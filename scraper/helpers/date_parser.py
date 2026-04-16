"""Преобразование строк даты из российских форматов (дд.мм.гггг) и ISO."""

from __future__ import annotations

import re
from datetime import date, datetime


def parse_russian_date(raw: str | None) -> date | None:
    if not raw:
        return None
    cleaned = re.sub(r"\s+", " ", str(raw).strip())
    m = re.search(r"(\d{1,2})[./](\d{1,2})[./](\d{2,4})", cleaned)
    if m is None:
        return None
    day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if year < 100:
        year += 2000 if year < 50 else 1900
    try:
        return date(year, month, day)
    except ValueError:
        return None


def to_date(raw: str | None) -> date | None:
    """Пробует ISO-формат, затем российский дд.мм.гггг."""
    if not raw:
        return None
    s = str(raw).strip()
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
    except ValueError:
        return parse_russian_date(s)
