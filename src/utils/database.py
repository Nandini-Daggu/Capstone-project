"""
src/utils/database.py
======================
SQLite database layer using SQLAlchemy.
Stores run history, audit logs, reports, and evaluation results.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from config.settings import settings

from .logger import get_logger

log = get_logger(__name__)


# ── SQLAlchemy Base ───────────────────────────────────────────────────────────


class Base(DeclarativeBase):
    pass


# ── ORM Models ────────────────────────────────────────────────────────────────


class RunRecord(Base):
    """One record per crew run."""

    __tablename__ = "runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(36), unique=True, nullable=False, index=True)
    status = Column(String(20), default="pending")
    industry = Column(String(200), default="")
    competitors = Column(Text, default="[]")  # JSON list
    region = Column(String(100), default="")
    time_period = Column(String(100), default="")
    max_sources = Column(Integer, default=15)
    max_steps = Column(Integer, default=25)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, default=0.0)
    sources_used = Column(Integer, default=0)
    steps_used = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    estimated_cost_usd = Column(Float, default=0.0)
    model_used = Column(String(100), default="")
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ReportRecord(Base):
    """Stored briefing reports."""

    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(36), unique=True, nullable=False, index=True)
    title = Column(String(500), default="Competitive Intelligence Briefing")
    industry = Column(String(200), default="")
    competitors = Column(Text, default="[]")
    full_markdown = Column(Text, default="")
    sources_json = Column(Text, default="[]")
    evaluation_json = Column(Text, nullable=True)
    review_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    approved = Column(Boolean, default=False)


class AuditLogRecord(Base):
    """Audit log records from the AuditLogger."""

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    record_id = Column(String(36), unique=True, nullable=False)
    run_id = Column(String(36), nullable=False, index=True)
    timestamp = Column(String(40))
    event_type = Column(String(50))
    agent = Column(String(100), nullable=True)
    tool = Column(String(100), nullable=True)
    model = Column(String(100), nullable=True)
    input_summary = Column(Text, nullable=True)
    output_summary = Column(Text, nullable=True)
    latency_ms = Column(Float, nullable=True)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    estimated_cost_usd = Column(Float, default=0.0)
    retries = Column(Integer, default=0)
    success = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)
    citation_count = Column(Integer, default=0)
    prompt_injection_detected = Column(Boolean, default=False)
    reviewer_approved = Column(Boolean, nullable=True)


class ObservabilityRecord(Base):
    """Observability / trace records."""

    __tablename__ = "observability"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(36), nullable=False, index=True)
    span_id = Column(String(36))
    agent = Column(String(100))
    operation = Column(String(200))
    started_at = Column(String(40))
    ended_at = Column(String(40))
    duration_ms = Column(Float, default=0.0)
    metadata_json = Column(Text, default="{}")
    success = Column(Boolean, default=True)
    error = Column(Text, nullable=True)


# ── Database Manager ──────────────────────────────────────────────────────────


class DatabaseManager:
    """Manages SQLite connection, schema creation, and CRUD operations."""

    def __init__(self) -> None:
        db_path = settings.database_url.replace("sqlite:///", "")
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        self._engine = create_engine(
            settings.database_url,
            echo=settings.database_echo,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        # Enable WAL mode for better concurrent reads
        @event.listens_for(self._engine, "connect")
        def set_sqlite_pragma(dbapi_conn, conn_record):  # noqa: ANN001
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        self._SessionFactory = sessionmaker(bind=self._engine, expire_on_commit=False)
        self._create_tables()
        log.info("Database initialised")

    def _create_tables(self) -> None:
        Base.metadata.create_all(self._engine)

    def get_session(self) -> Session:
        return self._SessionFactory()

    # ── Run CRUD ─────────────────────────────────────────────

    def create_run(self, run_data: Dict[str, Any]) -> RunRecord:
        with self.get_session() as session:
            record = RunRecord(**run_data)
            session.add(record)
            session.commit()
            session.refresh(record)
            return record

    def update_run(self, run_id: str, updates: Dict[str, Any]) -> None:
        with self.get_session() as session:
            record = session.query(RunRecord).filter_by(run_id=run_id).first()
            if record:
                for k, v in updates.items():
                    setattr(record, k, v)
                session.commit()

    def get_run(self, run_id: str) -> Optional[RunRecord]:
        with self.get_session() as session:
            return session.query(RunRecord).filter_by(run_id=run_id).first()

    def list_runs(self, limit: int = 20) -> List[RunRecord]:
        with self.get_session() as session:
            return session.query(RunRecord).order_by(RunRecord.created_at.desc()).limit(limit).all()

    # ── Report CRUD ───────────────────────────────────────────

    def save_report(self, report_data: Dict[str, Any]) -> ReportRecord:
        with self.get_session() as session:
            existing = session.query(ReportRecord).filter_by(run_id=report_data["run_id"]).first()
            if existing:
                for k, v in report_data.items():
                    setattr(existing, k, v)
                session.commit()
                return existing
            record = ReportRecord(**report_data)
            session.add(record)
            session.commit()
            session.refresh(record)
            return record

    def get_report(self, run_id: str) -> Optional[ReportRecord]:
        with self.get_session() as session:
            return session.query(ReportRecord).filter_by(run_id=run_id).first()

    def list_reports(self, limit: int = 20) -> List[ReportRecord]:
        with self.get_session() as session:
            return (
                session.query(ReportRecord)
                .order_by(ReportRecord.created_at.desc())
                .limit(limit)
                .all()
            )

    # ── Audit CRUD ────────────────────────────────────────────

    def save_audit_record(self, record_data: Dict[str, Any]) -> None:
        with self.get_session() as session:
            record = AuditLogRecord(**record_data)
            session.add(record)
            session.commit()

    def get_audit_logs(self, run_id: str) -> List[AuditLogRecord]:
        with self.get_session() as session:
            return (
                session.query(AuditLogRecord)
                .filter_by(run_id=run_id)
                .order_by(AuditLogRecord.id)
                .all()
            )

    # ── Observability ─────────────────────────────────────────

    def save_span(self, span_data: Dict[str, Any]) -> None:
        with self.get_session() as session:
            record = ObservabilityRecord(**span_data)
            session.add(record)
            session.commit()

    def get_trace(self, run_id: str) -> List[ObservabilityRecord]:
        with self.get_session() as session:
            return (
                session.query(ObservabilityRecord)
                .filter_by(run_id=run_id)
                .order_by(ObservabilityRecord.id)
                .all()
            )

    # ── Metrics ───────────────────────────────────────────────

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Aggregate metrics across all runs."""
        with self.get_session() as session:
            total_runs = session.query(RunRecord).count()
            completed = session.query(RunRecord).filter_by(status="completed").count()
            failed = session.query(RunRecord).filter_by(status="failed").count()

            # Aggregate from completed runs
            runs = session.query(RunRecord).filter_by(status="completed").all()
            if runs:
                avg_duration = sum(r.duration_seconds for r in runs) / len(runs)
                total_cost = sum(r.estimated_cost_usd for r in runs)
                total_tokens = sum(r.total_tokens for r in runs)
            else:
                avg_duration = total_cost = total_tokens = 0.0

            return {
                "total_runs": total_runs,
                "completed_runs": completed,
                "failed_runs": failed,
                "success_rate": completed / total_runs if total_runs > 0 else 0.0,
                "avg_duration_seconds": avg_duration,
                "total_cost_usd": total_cost,
                "total_tokens": total_tokens,
            }


# Singleton
db_manager = DatabaseManager()

__all__ = ["DatabaseManager", "db_manager", "RunRecord", "ReportRecord", "AuditLogRecord"]
