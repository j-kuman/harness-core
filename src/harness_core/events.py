from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EventType(StrEnum):
    run_started = "run_started"
    task_received = "task_received"
    model_call_started = "model_call_started"
    model_call_completed = "model_call_completed"
    file_read = "file_read"
    file_edited = "file_edited"
    command_completed = "command_completed"
    validator_completed = "validator_completed"
    decision_made = "decision_made"
    approval_requested = "approval_requested"
    approval_resolved = "approval_resolved"
    human_override = "human_override"
    run_completed = "run_completed"
    run_failed = "run_failed"


DEFERRED_EVENT_TYPES = frozenset(
    {
        "context_loaded",
        "model_selected",
        "plan_created",
        "file_edit_intent",
        "command_intent",
        "validator_started",
        "reviewer_started",
        "reviewer_completed",
        "approval_granted",
        "approval_denied",
        "memory_write_requested",
        "memory_write_approved",
        "shadow_review",
        "policy_calibration_run",
        "autonomy_level_adjusted",
    }
)


class BaseEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1)
    seq: int = Field(ge=0)
    timestamp: str = Field(min_length=1)
    event_type: EventType
    agent: str = Field(min_length=1)
    payload: dict[str, Any]


REQUIRED_PAYLOAD_KEYS: dict[EventType, dict[str, Any]] = {
    EventType.run_started: {"task_summary": str},
    EventType.task_received: {"task": str},
    EventType.model_call_started: {"model": str},
    EventType.model_call_completed: {
        "model": str,
        "tokens_in": ("int_ge_0",),
        "tokens_out": ("int_ge_0",),
        "latency_ms": ("int_ge_0",),
        "status": ("enum", {"ok", "error"}),
    },
    EventType.file_read: {"path": str},
    EventType.file_edited: {"path": str, "summary": str},
    EventType.command_completed: {"command": str, "exit_code": int, "summary": str},
    EventType.validator_completed: {"validator": str, "passed": bool, "errors": list},
    EventType.decision_made: {
        "decision_type": str,
        "choice": str,
        "confidence": ("float_range", 0.0, 1.0),
        "autonomy_level": ("enum", {"auto", "notify", "review", "escalate"}),
    },
    EventType.approval_requested: {"request_id": str, "prompt": str},
    EventType.approval_resolved: {
        "request_id": str,
        "outcome": ("enum", {"granted", "denied"}),
    },
    EventType.human_override: {
        "decision_ref": int,
        "human_choice": str,
        "reason": str,
    },
    EventType.run_completed: {"outcome": ("enum", {"success", "partial", "failure"})},
    EventType.run_failed: {"error": str},
}
