#!/usr/bin/env python3
"""Генерация тестового .xlsx с ИНН (120+ строк) для проверки массового ввода."""

from __future__ import annotations

import sys
from pathlib import Path

from openpyxl import Workbook

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT = PROJECT_ROOT / "input" / "sample_inns.xlsx"


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "inns"
    ws.append(["ИНН"])

    real_inns = ["231138771115"]
    for idx in range(120):
        if idx < len(real_inns):
            ws.append([real_inns[idx]])
        else:
            ws.append([f"77{idx:010d}"[:12]])

    wb.save(OUTPUT)
    print(f"Создан файл: {OUTPUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
