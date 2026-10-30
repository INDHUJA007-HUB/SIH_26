"""Explicit, source-linked policy. Demo presets never become statutory rules."""

from datetime import UTC, datetime, timedelta
from string import Formatter
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


def aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("An explicit timezone is required")
    return value.astimezone(UTC)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Reminder(StrictModel):
    key: str = Field(pattern=r"^[A-Z0-9_]{1,40}$")
    offset_seconds: int = Field(ge=-31536000, le=31536000)
    recipient_role: Literal[
        "INSTITUTION", "OFFICER", "REGIONAL", "BUREAU", "COMMITTEE", "AUTHORITY"
    ]


class Stage(StrictModel):
    key: str = Field(pattern=r"^[A-Z0-9_]{1,50}$")
    actor_role: Literal["OFFICER", "REGIONAL", "BUREAU", "COMMITTEE", "AUTHORITY"]
    next: dict[str, str] = Field(default_factory=dict)
    required_obligations: list[str] = Field(default_factory=list)
    requires_evc_report: bool = False
    terminal: bool = False
    decision: bool = False
    evc_queue: bool = False
    target_seconds: int | None = Field(default=None, ge=60, le=31536000)


class Selector(StrictModel):
    category: str = Field(min_length=1, max_length=50)
    route: str


class ProcessPack(StrictModel):
    name: str = Field(min_length=3, max_length=160)
    source_reference: str = Field(min_length=3, max_length=1000)
    academic_cycle: int = Field(ge=2024, le=2100)
    demo_only: bool = True
    calendar_basis: Literal["ELAPSED_SECONDS"] = "ELAPSED_SECONDS"
    pause_authorized: bool = False
    stages: list[Stage] = Field(min_length=2, max_length=50)
    routes: dict[str, str] = Field(min_length=1, max_length=30)
    selectors: list[Selector] = Field(min_length=1, max_length=100)
    reminders: list[Reminder] = Field(default_factory=list, max_length=20)
    evc_scheduling_seconds: int | None = Field(default=None, ge=60, le=31536000)
    evc_report_seconds: int | None = Field(default=None, ge=60, le=31536000)
    evc_report_clock: Literal["ACTUAL_COMPLETION", "PLANNED_END", "CONFIRMATION"] = (
        "ACTUAL_COMPLETION"
    )
    new_institution_categories: list[str] = Field(default_factory=list, max_length=100)
    notice_templates: dict[str, str] = Field(default_factory=dict, max_length=20)

    @model_validator(mode="after")
    def validate_graph(self) -> "ProcessPack":
        by_key = {stage.key: stage for stage in self.stages}
        if len(by_key) != len(self.stages):
            raise ValueError("Stage keys must be unique")
        if len({item.category for item in self.selectors}) != len(self.selectors):
            raise ValueError("Route selection must be unambiguous")
        if len({r.key for r in self.reminders}) != len(self.reminders):
            raise ValueError("Reminder keys must be unique")
        fields = {"case_reference", "institution_reference", "stage", "reason", "generated_at"}
        for template in self.notice_templates.values():
            if len(template) > 10000:
                raise ValueError("Communication templates are limited to 10000 characters")
            for _, field, spec, conversion in Formatter().parse(template):
                if field is not None and (field not in fields or spec or conversion):
                    raise ValueError("Use only the supported communication placeholders")
        if any(item.route not in self.routes for item in self.selectors):
            raise ValueError("Selector references an unknown route")
        if any(start not in by_key for start in self.routes.values()):
            raise ValueError("Route references an unknown starting stage")
        for stage in self.stages:
            if any(target not in by_key for target in stage.next.values()):
                raise ValueError("Transition references an unknown stage")
            if stage.terminal and stage.next:
                raise ValueError("Terminal stages cannot advance")
            if stage.decision and stage.actor_role != "AUTHORITY":
                raise ValueError("Decisions require competent authority")
        # Cycles are allowed for returns, but every configured stage must reach closure.
        closable = {s.key for s in self.stages if s.terminal}
        for _ in self.stages:
            closable |= {s.key for s in self.stages if set(s.next.values()) & closable}
        if set(by_key) != closable:
            raise ValueError("Every stage must have a path to closure")
        return self

    def stage(self, key: str) -> Stage:
        return next(s for s in self.stages if s.key == key)


def time_condition(due: datetime | None, at: datetime) -> str:
    if due is None:
        return "UNSPECIFIED"
    delta = (aware(due) - aware(at)).total_seconds()
    return "OVERDUE" if delta < 0 else "DUE" if delta == 0 else "UPCOMING"


def clock(received: datetime, pauses: list[dict[str, str | None]], at: datetime) -> dict[str, int]:
    end = aware(at)
    start = aware(received)
    elapsed = max(0, int((end - start).total_seconds()))
    excluded = 0
    for item in pauses:
        begin = max(start, aware(datetime.fromisoformat(str(item["start"]))))
        finish = min(end, aware(datetime.fromisoformat(str(item["end"])))) if item["end"] else end
        excluded += max(0, int((finish - begin).total_seconds()))
    return {
        "total_elapsed_seconds": elapsed,
        "excluded_seconds": excluded,
        "accountable_seconds": max(0, elapsed - excluded),
    }


def due_after(at: datetime, seconds: int | None) -> datetime | None:
    return aware(at) + timedelta(seconds=seconds) if seconds else None
