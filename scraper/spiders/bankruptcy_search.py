"""
Паук ЕФРСБ: загрузка ИНН, запросы к API физлиц и юрлиц, сбор номеров дел.

Эндпоинты — /backend/prsnbankrupts и /backend/cmpbankrupts (JSON).
По каждому ИНН выполняются оба запроса последовательно, результаты объединяются.
"""

from __future__ import annotations

import os
from typing import AsyncIterator

import scrapy
from scrapy.http import Response
from sqlalchemy import select

from scraper.api_clients import bankruptcy_registry as registry
from scraper.helpers.excel_reader import read_inns_from_string, read_inns_from_xlsx
from scraper.items import FedresursFinishedItem, FedresursInsolvencyItem
from storage.models import CompletedInn
from storage.session import managed_session


class BankruptcySearchSpider(scrapy.Spider):
    name = "bankruptcy_search"
    allowed_domains = ["fedresurs.ru", "bankrot.fedresurs.ru"]

    def __init__(
        self,
        xlsx_path: str | None = None,
        inns: str | None = None,
        sheet: str | None = None,
        column: str | None = None,
        skip_processed: str = "true",
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self._xlsx = xlsx_path or os.environ.get("INPUT_XLSX")
        self._raw_inns = inns or os.environ.get("INNS")
        self._sheet = sheet or os.environ.get("INPUT_XLSX_SHEET")
        self._col = column or os.environ.get("INPUT_XLSX_COLUMN")
        self._skip = str(skip_processed).lower() in ("1", "true", "yes", "on")
        self._inn_list = self._collect_inns()

    def _collect_inns(self) -> list[str]:
        if self._xlsx:
            return read_inns_from_xlsx(self._xlsx, sheet_name=self._sheet, column=self._col)
        return read_inns_from_string(self._raw_inns)

    async def start(self) -> AsyncIterator[scrapy.Request]:
        if not self._inn_list:
            self.logger.error("Список ИНН пуст — укажите INPUT_XLSX или -a inns=...")
            return
        for inn in self._inn_list:
            if self._skip and self._is_processed(inn):
                self.logger.info("Пропуск ИНН %s — уже обработан ранее", inn)
                continue
            yield scrapy.Request(
                url=registry.persons_url(inn),
                callback=self._on_persons_response,
                cb_kwargs={"inn": inn},
                headers=registry.REQUEST_HEADERS,
                dont_filter=True,
                meta={"playwright": False},
            )

    def _is_processed(self, inn: str) -> bool:
        try:
            with managed_session() as db:
                hit = db.execute(
                    select(CompletedInn).where(CompletedInn.inn == inn)
                ).scalar_one_or_none()
                return hit is not None
        except Exception as exc:
            self.logger.warning("Не удалось проверить completed_inns: %s", exc)
            return False

    def _on_persons_response(self, response: Response, inn: str):
        collected: set[str] = set()
        persons_error: str | None = None

        try:
            data = registry.decode_response(response.text)
            for case_no, dt in registry.extract_cases(data):
                collected.add(case_no.casefold())
                yield FedresursInsolvencyItem(
                    inn=inn,
                    case_number=case_no,
                    last_event_date=dt,
                    error=None,
                )
        except Exception as exc:
            persons_error = str(exc)
            self.logger.warning("Ошибка парсинга prsnbankrupts для ИНН %s: %s", inn, exc)

        yield scrapy.Request(
            url=registry.companies_url(inn),
            callback=self._on_companies_response,
            cb_kwargs={"inn": inn, "collected": collected, "persons_error": persons_error},
            headers=registry.REQUEST_HEADERS,
            dont_filter=True,
            meta={"playwright": False},
        )

    def _on_companies_response(
        self,
        response: Response,
        inn: str,
        collected: set[str],
        persons_error: str | None,
    ):
        companies_error: str | None = None

        try:
            data = registry.decode_response(response.text)
            for case_no, dt in registry.extract_cases(data):
                if case_no.casefold() in collected:
                    continue
                collected.add(case_no.casefold())
                yield FedresursInsolvencyItem(
                    inn=inn,
                    case_number=case_no,
                    last_event_date=dt,
                    error=None,
                )
        except Exception as exc:
            companies_error = str(exc)
            self.logger.warning("Ошибка парсинга cmpbankrupts для ИНН %s: %s", inn, exc)

        if not collected:
            yield FedresursInsolvencyItem(
                inn=inn,
                case_number="",
                last_event_date=None,
                error=persons_error or companies_error or "not_found",
            )

        yield FedresursFinishedItem(inn=inn)
