"""
Клиент ЕФРСБ (bankrot.fedresurs.ru): формирование URL, заголовки, разбор JSON.

При поиске по ИНН на bankrot.fedresurs.ru браузер шлёт XHR:
  GET /backend/prsnbankrupts?searchString=...&limit=15&offset=0  (физлица)
  GET /backend/cmpbankrupts?searchString=...&limit=15&offset=0   (юрлица)

Без корректного Referer/Origin сервер возвращает 403.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlencode

EFRSB_BASE = "https://bankrot.fedresurs.ru"

REQUEST_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Referer": f"{EFRSB_BASE}/bankrupts",
    "Origin": EFRSB_BASE,
}


def persons_url(inn: str, limit: int = 15, offset: int = 0) -> str:
    qs = urlencode({"searchString": inn, "limit": limit, "offset": offset})
    return f"{EFRSB_BASE}/backend/prsnbankrupts?{qs}"


def companies_url(inn: str, limit: int = 15, offset: int = 0) -> str:
    qs = urlencode({"searchString": inn, "limit": limit, "offset": offset})
    return f"{EFRSB_BASE}/backend/cmpbankrupts?{qs}"


def decode_response(body: str) -> dict[str, Any]:
    return json.loads(body)


def extract_cases(data: dict[str, Any]) -> list[tuple[str, str | None]]:
    """Извлекает уникальные пары (номер_дела, ISO-дата статуса) из ответа API."""
    result: list[tuple[str, str | None]] = []
    known: set[str] = set()

    for entry in data.get("pageData") or []:
        legal_case = entry.get("lastLegalCase") or {}
        number = (legal_case.get("number") or "").strip()
        if not number:
            continue

        status = legal_case.get("status") or {}
        raw_date = status.get("date")
        event_date: str | None = raw_date if isinstance(raw_date, str) else None

        key = number.casefold()
        if key in known:
            continue
        known.add(key)
        result.append((number, event_date))

    return result
