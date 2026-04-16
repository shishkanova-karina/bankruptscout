"""ORM-модели для хранения результатов сбора данных о банкротствах и арбитражных делах."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class InsolvencyRecord(Base):
    """Запись о банкротстве из ЕФРСБ: ИНН должника, номер дела, дата последнего события."""

    __tablename__ = "insolvency_records"
    __table_args__ = (
        UniqueConstraint("inn", "case_number", name="uq_insolvency_inn_case"),
        Index("ix_insolvency_records_inn", "inn"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    inn: Mapped[str] = mapped_column(String(32), nullable=False)
    case_number: Mapped[str] = mapped_column(String(128), nullable=False)
    last_event_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), default=datetime.utcnow
    )
    error_info: Mapped[str | None] = mapped_column(Text, nullable=True)

    court_docs: Mapped[list[ArbitrationDocument]] = relationship(
        back_populates="insolvency",
        foreign_keys="ArbitrationDocument.insolvency_id",
    )


class ArbitrationDocument(Base):
    """Документ из электронного дела КАД: наименование, дата, ссылка."""

    __tablename__ = "arbitration_documents"
    __table_args__ = (
        UniqueConstraint(
            "case_number",
            "doc_title",
            "last_event_date",
            name="uq_arb_doc_event",
        ),
        Index("ix_arbitration_docs_case", "case_number"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    insolvency_id: Mapped[int | None] = mapped_column(
        ForeignKey("insolvency_records.id", ondelete="SET NULL"),
        nullable=True,
    )
    case_number: Mapped[str] = mapped_column(String(128), nullable=False)
    last_event_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    doc_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    doc_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), default=datetime.utcnow
    )
    error_info: Mapped[str | None] = mapped_column(Text, nullable=True)

    insolvency: Mapped[InsolvencyRecord | None] = relationship(
        back_populates="court_docs",
        foreign_keys=[insolvency_id],
    )


class CompletedInn(Base):
    """Отметка об обработанном ИНН на этапе ЕФРСБ для возобновления при перезапуске."""

    __tablename__ = "completed_inns"
    __table_args__ = (UniqueConstraint("inn", name="uq_completed_inn"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    inn: Mapped[str] = mapped_column(String(32), nullable=False)
    finished_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), default=datetime.utcnow
    )
    run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
