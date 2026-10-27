"""Foundation database metadata; Phase 2 adds production authorization/RLS tables."""

from datetime import datetime
from typing import Any

from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.trace import TracerProvider
from sqlalchemy import JSON, Boolean, DateTime, String, create_engine, func
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class FoundationInstitution(Base):
    __tablename__ = "foundation_institutions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(200))
    synthetic: Mapped[bool] = mapped_column(Boolean, default=True)


class SeedRuleCandidate(Base):
    __tablename__ = "seed_rule_candidates"
    rule_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    publication_state: Mapped[str] = mapped_column(String(30), default="DRAFT")
    production_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    adverse_action_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    source_sha256: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


def build_engine(url: str, provider: TracerProvider | None = None) -> Engine:
    engine = create_engine(
        url,
        pool_pre_ping=True,
        pool_size=3,
        max_overflow=2,
        connect_args={"connect_timeout": 3},
    )
    if provider is not None:
        # Statement text/parameters can contain identifiers: remove db.statement before export.
        SQLAlchemyInstrumentor().instrument(
            engine=engine, tracer_provider=provider, enable_commenter=False
        )
    return engine
