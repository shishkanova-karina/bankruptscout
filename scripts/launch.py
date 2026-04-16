#!/usr/bin/env python3
"""Последовательный запуск пауков: сначала ЕФРСБ, затем КАД. Вывод результатов."""

from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)
os.environ.setdefault("PYTHONPATH", str(PROJECT_ROOT))

sample = PROJECT_ROOT / "input" / "sample_inns.xlsx"
if sample.exists() and not os.environ.get("INPUT_XLSX"):
    os.environ["INPUT_XLSX"] = str(sample)

from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

from storage.session import initialize_tables, managed_session


def print_results() -> None:
    from storage.models import ArbitrationDocument, InsolvencyRecord

    from sqlalchemy import select

    print("\n" + "=" * 80)
    print("РЕЗУЛЬТАТЫ СБОРА ДАННЫХ")
    print("=" * 80)

    with managed_session() as db:
        records = db.execute(
            select(InsolvencyRecord).order_by(InsolvencyRecord.id)
        ).scalars().all()

        print(f"\n--- ЕФРСБ: найдено {len(records)} записей ---")
        for r in records:
            print(
                f"  ИНН: {r.inn}  |  Дело: {r.case_number}  |  "
                f"Дата: {r.last_event_date}  |  Ошибка: {r.error_info or '—'}"
            )

        docs = db.execute(
            select(ArbitrationDocument).order_by(ArbitrationDocument.id)
        ).scalars().all()

        print(f"\n--- КАД: найдено {len(docs)} документов ---")
        for d in docs:
            print(
                f"  Дело: {d.case_number}  |  Документ: {d.doc_title}  |  "
                f"Дата: {d.last_event_date}  |  URL: {d.doc_link or '—'}  |  "
                f"Ошибка: {d.error_info or '—'}"
            )

    print("\n" + "=" * 80)


def main() -> None:
    initialize_tables()
    cfg = get_project_settings()
    runner = CrawlerProcess(cfg)
    runner.crawl("bankruptcy_search")
    runner.crawl("court_docs")
    runner.start()
    print_results()


if __name__ == "__main__":
    main()
