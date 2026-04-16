"""
Клиент КАД (kad.arbitr.ru): поиск дел, разбор HTML результатов и карточки.

POST /Kad/SearchInstances принимает JSON (как returnRequestInfo() во фронте),
возвращает HTML-фрагмент с таблицей #b-cases. Карточка дела — GET /Card/{guid}.

При автоматических запросах возможна блокировка (blocked.png / captcha).
"""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urljoin

from parsel import Selector

SEARCH_ENDPOINT = "https://kad.arbitr.ru/Kad/SearchInstances"
BASE_URL = "https://kad.arbitr.ru"

SEARCH_HEADERS = {
    "Content-Type": "application/json; charset=utf-8",
    "Accept": "text/html, */*; q=0.01",
    "Referer": f"{BASE_URL}/",
    "Origin": BASE_URL,
    "X-Requested-With": "XMLHttpRequest",
    "x-date-format": "iso",
}

CARD_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": f"{BASE_URL}/",
}


def make_search_payload(cases: list[str], page: int = 1, per_page: int = 25) -> bytes:
    payload: dict[str, Any] = {
        "Page": page,
        "Count": per_page,
        "Courts": [],
        "DateFrom": None,
        "DateTo": None,
        "Sides": [],
        "Judges": [],
        "CaseNumbers": cases,
        "WithVKSInstances": False,
    }
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def detect_block(html: str) -> bool:
    if not html:
        return True
    content = html.lower()
    markers = ("blocked.png", "подозрительная активность", "pravocaptcha")
    if "blocked.png" in content and "доступ" in content:
        return True
    return any(m in content for m in markers)


def _normalize(s: str) -> str:
    return (
        s.replace("\u0410", "A")
        .replace("\u0430", "a")
        .replace(" ", "")
        .strip()
        .upper()
    )


def _case_in_row(row_text: str, target: str) -> bool:
    return (
        target.upper().replace(" ", "") in row_text.upper().replace(" ", "")
        or _normalize(target) in _normalize(row_text)
    )


def find_card_links(html: str, target_case: str) -> list[str]:
    """Находит ссылки /Card/{guid} в таблице результатов поиска."""
    sel = Selector(text=html)
    links: list[str] = []
    visited: set[str] = set()

    for row in sel.css("table#b-cases tr"):
        text = " ".join(row.xpath(".//text()").getall())
        if not _case_in_row(text, target_case):
            continue
        for href in row.css("a::attr(href)").getall():
            if not href or "/Card/" not in href:
                continue
            full = href if href.startswith("http") else urljoin(f"{BASE_URL}/", href.lstrip("/"))
            if full not in visited:
                visited.add(full)
                links.append(full)

    if not links:
        for href in sel.css("a[href*='/Card/']::attr(href)").getall():
            full = href if href.startswith("http") else urljoin(f"{BASE_URL}/", href.lstrip("/"))
            if full not in visited:
                visited.add(full)
                links.append(full)

    return links


def parse_last_document(html: str) -> tuple[str | None, str | None, str | None]:
    """
    Разбирает HTML карточки, ищет последний документ (дата, название, url).
    Возвращает (дата, название, url) или тройку None.
    """
    if not html or detect_block(html):
        return None, None, None

    sel = Selector(text=html)
    all_text = " ".join(sel.xpath("//body//text()").getall())

    rows: list[tuple[str | None, str, str | None]] = []
    for tr in sel.css("table tr"):
        content = " ".join(t.strip() for t in tr.xpath(".//text()").getall() if t.strip())
        if len(content) < 5:
            continue

        href = tr.css("a::attr(href)").get()
        anchor = " ".join(tr.css("a::text").getall()).strip()
        date_match = re.search(r"(\d{1,2})[./](\d{1,2})[./](\d{2,4})", content)
        dt = date_match.group(0) if date_match else None
        label = anchor or content

        if href and not href.startswith("http"):
            href = urljoin(BASE_URL + "/", href)
        rows.append((dt, label, href))

    if rows:
        return rows[-1]

    date_match = re.search(r"(\d{1,2})[./](\d{1,2})[./](\d{2,4})", all_text)
    return (date_match.group(0) if date_match else None, None, None)
