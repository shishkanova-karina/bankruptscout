"""Pipeline: сохранение собранных элементов в реляционную БД."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from scraper.items import (
    FedresursFinishedItem,
    FedresursInsolvencyItem,
    KadDocumentItem,
    KadFinishedItem,
)
from storage.models import ArbitrationDocument, CompletedInn, InsolvencyRecord
from storage.session import build_session_maker

log = logging.getLogger(__name__)


class StoragePipeline:
    def open_spider(self, spider) -> None:
        self._session_factory = build_session_maker()

    def close_spider(self, spider) -> None:
        pass

    def process_item(self, item: Any, spider) -> Any:
        db = self._session_factory()
        try:
            self._dispatch(db, item)
            db.commit()
        except Exception:
            db.rollback()
            log.exception("Ошибка сохранения: %s", item)
            raise
        finally:
            db.close()
        return item

    def _dispatch(self, db: Session, item: Any) -> None:
        if isinstance(item, FedresursInsolvencyItem):
            self._upsert_insolvency(db, item)
        elif isinstance(item, FedresursFinishedItem):
            self._mark_inn_done(db, item["inn"])
        elif isinstance(item, KadDocumentItem):
            self._upsert_document(db, item)
        elif isinstance(item, KadFinishedItem):
            pass

    def _coerce_date(self, raw):
        if raw is None:
            return None
        if hasattr(raw, "date"):
            return raw.date()
        if isinstance(raw, str):
            from scraper.helpers.date_parser import to_date
            return to_date(raw)
        return raw

    def _upsert_insolvency(self, db: Session, item: FedresursInsolvencyItem) -> None:
        inn = item.get("inn")
        cn = (item.get("case_number") or "").strip()
        err = item.get("error")
        evt = self._coerce_date(item.get("last_event_date"))

        if not cn:
            if err:
                log.warning("ЕФРСБ: ИНН %s — %s", inn, err)
            return

        existing = db.execute(
            select(InsolvencyRecord).where(
                InsolvencyRecord.inn == inn,
                InsolvencyRecord.case_number == cn,
            )
        ).scalar_one_or_none()

        ts = datetime.utcnow()
        if existing is not None:
            existing.last_event_date = evt
            existing.collected_at = ts
            existing.error_info = err
        else:
            db.add(InsolvencyRecord(
                inn=inn,
                case_number=cn,
                last_event_date=evt,
                collected_at=ts,
                error_info=err,
            ))

    def _mark_inn_done(self, db: Session, inn: str) -> None:
        row = db.execute(
            select(CompletedInn).where(CompletedInn.inn == inn)
        ).scalar_one_or_none()

        ts = datetime.utcnow()
        if row is not None:
            row.finished_at = ts
        else:
            db.add(CompletedInn(inn=inn, finished_at=ts))

    def _upsert_document(self, db: Session, item: KadDocumentItem) -> None:
        cn = (item.get("case_number") or "").strip()
        if not cn:
            return

        err = item.get("error")
        evt = self._coerce_date(item.get("last_event_date"))
        title = (item.get("document_name") or "").strip() or None
        link = (item.get("document_url") or "").strip() or None

        parent = db.execute(
            select(InsolvencyRecord)
            .where(InsolvencyRecord.case_number == cn)
            .limit(1)
        ).scalar_one_or_none()
        parent_id = parent.id if parent else None

        ts = datetime.utcnow()

        if err and not title:
            log.warning("КАД: дело %s — %s", cn, err)
            err_row = db.execute(
                select(ArbitrationDocument).where(
                    ArbitrationDocument.case_number == cn,
                    ArbitrationDocument.doc_title == "(error)",
                )
            ).scalar_one_or_none()

            if err_row is not None:
                err_row.error_info = err
                err_row.collected_at = ts
            else:
                db.add(ArbitrationDocument(
                    insolvency_id=parent_id,
                    case_number=cn,
                    last_event_date=None,
                    doc_title="(error)",
                    doc_link=None,
                    collected_at=ts,
                    error_info=err,
                ))
            return

        existing = db.execute(
            select(ArbitrationDocument).where(
                ArbitrationDocument.case_number == cn,
                ArbitrationDocument.doc_title == title,
                ArbitrationDocument.last_event_date == evt,
            )
        ).scalar_one_or_none()

        if existing is not None:
            existing.doc_link = link
            existing.collected_at = ts
            existing.error_info = err
            existing.insolvency_id = parent_id or existing.insolvency_id
        else:
            db.add(ArbitrationDocument(
                insolvency_id=parent_id,
                case_number=cn,
                last_event_date=evt,
                doc_title=title,
                doc_link=link,
                collected_at=ts,
                error_info=err,
            ))
