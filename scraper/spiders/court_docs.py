"""
Паук КАД: поиск дел через POST /Kad/SearchInstances, переход на карточку /Card/{guid},
разбор HTML. При блокировке возможен fallback через Playwright.
"""

from __future__ import annotations

import os
import re
from typing import AsyncIterator

import scrapy
from scrapy.http import Response
from sqlalchemy import select

from scraper.api_clients import court_portal as portal
from scraper.items import KadDocumentItem, KadFinishedItem
from storage.models import ArbitrationDocument, InsolvencyRecord
from storage.session import managed_session

KAD_HOMEPAGE = "https://kad.arbitr.ru/"


class ArbitrationCourtSpider(scrapy.Spider):
    name = "court_docs"
    allowed_domains = ["kad.arbitr.ru"]
    custom_settings = {
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": int(
            os.environ.get("PLAYWRIGHT_NAV_TIMEOUT_MS", "120000")
        ),
    }

    def __init__(
        self,
        case_numbers: str | None = None,
        skip_existing: str = "true",
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self._raw_cases = case_numbers or os.environ.get("KAD_CASE_NUMBERS")
        self._skip = str(skip_existing).lower() in ("1", "true", "yes", "on")
        self._playwright = os.environ.get("KAD_USE_PLAYWRIGHT", "false").lower() in (
            "1", "true", "yes", "on",
        )

    async def start(self) -> AsyncIterator[scrapy.Request]:
        cases = self._load_case_numbers()
        if not cases:
            self.logger.warning("Нет номеров дел — сначала запустите bankruptcy_search или задайте -a case_numbers=...")
            return

        for cn in cases:
            if self._skip and self._doc_exists(cn):
                self.logger.info("Пропуск дела %s — данные КАД уже собраны", cn)
                continue
            yield scrapy.Request(
                url=portal.SEARCH_ENDPOINT,
                method="POST",
                body=portal.make_search_payload([cn]),
                headers=portal.SEARCH_HEADERS,
                callback=self._on_search_result,
                cb_kwargs={"case_number": cn},
                dont_filter=True,
                meta={"playwright": False},
            )

    def _load_case_numbers(self) -> list[str]:
        if self._raw_cases:
            parts = re.split(r"[,\s;]+", self._raw_cases.strip())
            return list(dict.fromkeys(p.strip() for p in parts if p.strip()))
        try:
            with managed_session() as db:
                rows = db.execute(
                    select(InsolvencyRecord.case_number).distinct()
                ).scalars().all()
            return [r for r in rows if r and r.strip()]
        except Exception as exc:
            self.logger.error("Не удалось получить номера дел из БД: %s", exc)
            return []

    def _doc_exists(self, case_number: str) -> bool:
        try:
            with managed_session() as db:
                hit = db.execute(
                    select(ArbitrationDocument.id).where(
                        ArbitrationDocument.case_number == case_number,
                        ArbitrationDocument.doc_title.isnot(None),
                    ).limit(1)
                ).scalar_one_or_none()
                return hit is not None
        except Exception:
            return False

    def _on_search_result(self, response: Response, case_number: str):
        body = response.text

        if portal.detect_block(body):
            self.logger.warning(
                "Антибот/блокировка КАД для дела %s (HTTP %s)%s",
                case_number,
                response.status,
                " — fallback через Playwright" if self._playwright else "",
            )
            if self._playwright:
                yield scrapy.Request(
                    url=KAD_HOMEPAGE,
                    callback=self._on_playwright_page,
                    dont_filter=True,
                    meta={
                        "playwright": True,
                        "playwright_include_page": True,
                        "case_number": case_number,
                    },
                )
            else:
                yield KadDocumentItem(
                    case_number=case_number,
                    last_event_date=None,
                    document_name=None,
                    document_url=None,
                    error="antibot_or_blocked_http",
                )
                yield KadFinishedItem(case_number=case_number)
            return

        card_urls = portal.find_card_links(body, case_number)
        if not card_urls:
            self.logger.warning("Карточка дела %s не найдена в результатах поиска", case_number)
            yield KadDocumentItem(
                case_number=case_number,
                last_event_date=None,
                document_name=None,
                document_url=None,
                error="case_card_not_found",
            )
            yield KadFinishedItem(case_number=case_number)
            return

        yield scrapy.Request(
            url=card_urls[0],
            callback=self._on_card_page,
            cb_kwargs={"case_number": case_number},
            headers=portal.CARD_HEADERS,
            dont_filter=True,
            meta={"playwright": False},
        )

    def _on_card_page(self, response: Response, case_number: str):
        dt, name, url = portal.parse_last_document(response.text)
        err = None
        if portal.detect_block(response.text):
            err = "antibot_on_card_page"
        elif not name:
            err = "electronic_case_parse_empty"

        yield KadDocumentItem(
            case_number=case_number,
            last_event_date=dt,
            document_name=name,
            document_url=url,
            error=err,
        )
        yield KadFinishedItem(case_number=case_number)

    def _on_playwright_page(self, response: Response):
        from playwright.sync_api import Page

        page: Page = response.meta["playwright_page"]
        cn = response.meta["case_number"]
        error: str | None = None
        dt = name = url = None

        try:
            page.wait_for_load_state("domcontentloaded", timeout=90000)
            page.wait_for_timeout(2000)

            if _check_captcha(page):
                error = "captcha_or_block"
            else:
                _type_case_number(page, cn)
                page.wait_for_timeout(3000)
                _click_first_result(page, cn)
                page.wait_for_timeout(3000)
                _switch_to_edoc_tab(page)
                page.wait_for_timeout(2000)
                dt, name, url = _scrape_last_doc_row(page)
        except Exception as exc:
            self.logger.exception("Playwright, дело %s: %s", cn, exc)
            error = str(exc)

        yield KadDocumentItem(
            case_number=cn,
            last_event_date=dt,
            document_name=name,
            document_url=url,
            error=error,
        )
        yield KadFinishedItem(case_number=cn)


def _check_captcha(page) -> bool:
    try:
        html = page.content().lower()
    except Exception:
        return False
    triggers = ("captcha", "капча", "blocked.png", "доступ ограничен", "robot")
    return any(t in html for t in triggers)


def _type_case_number(page, case_number: str) -> None:
    selectors = [
        'input[placeholder*="дела"]',
        'input[placeholder*="Дела"]',
        'input[type="search"]',
        'input[type="text"]',
    ]
    for css in selectors:
        try:
            el = page.locator(css).first
            if el.count() > 0:
                el.fill(case_number, timeout=8000)
                el.press("Enter")
                return
        except Exception:
            continue


def _click_first_result(page, case_number: str) -> None:
    try:
        hit = page.get_by_text(case_number, exact=False).first
        if hit.count() > 0:
            hit.click(timeout=8000)
    except Exception:
        pass


def _switch_to_edoc_tab(page) -> None:
    labels = ("Электронное дело", "электронное дело")
    for text in labels:
        try:
            tab = page.get_by_role("tab", name=re.compile(text, re.I)).first
            if tab.count() > 0:
                tab.click(timeout=8000)
                return
        except Exception:
            pass
        try:
            page.get_by_text(text, exact=False).first.click(timeout=8000)
            return
        except Exception:
            pass


def _scrape_last_doc_row(page):
    dt = name = url = None
    try:
        rows = page.locator("table tbody tr, [role='row']").all()
        if not rows:
            return dt, name, url
        last = rows[-1]
        text = last.inner_text()
        m = re.search(r"\d{1,2}[./]\d{1,2}[./]\d{2,4}", text)
        if m:
            dt = m.group(0)
        anchor = last.locator("a").first
        if anchor.count() > 0:
            name = anchor.inner_text().strip() or text.strip()
            try:
                url = anchor.get_attribute("href")
            except Exception:
                url = None
        else:
            pieces = [p.strip() for p in text.split("\n") if p.strip()]
            if pieces:
                name = pieces[-1]
    except Exception:
        pass
    return dt, name, url
