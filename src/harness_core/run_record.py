from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel
from typing import Literal


class RunRecord(BaseModel):
    run_id: str
    started_at: str
    ended_at: str | None
    status: Literal["running", "completed", "failed"]
    task_summary: str
    models_used: list[str]
    event_count: int
    invalid_count: int
    outcome: str | None


def build_run_record(run_dir: Path) -> RunRecord:
    run_dir = Path(run_dir)
    events = _read_jsonl(run_dir / "events.jsonl")
    invalid_count = _line_count(run_dir / "events.invalid.jsonl")

    if not events:
        raise ValueError(f"no valid events found in {run_dir}")

    run_id = run_dir.name
    first_event = events[0]
    run_started = next((event for event in events if event["event_type"] == "run_started"), None)
    terminal = next(
        (event for event in reversed(events) if event["event_type"] in {"run_completed", "run_failed"}),
        None,
    )

    if terminal is None:
        status = "running"
        ended_at = None
        outcome = None
    elif terminal["event_type"] == "run_completed":
        status = "completed"
        ended_at = terminal["timestamp"]
        outcome = terminal["payload"]["outcome"]
    else:
        status = "failed"
        ended_at = terminal["timestamp"]
        outcome = None

    models_used = sorted(
        {
            event["payload"]["model"]
            for event in events
            if event["event_type"] in {"model_call_started", "model_call_completed"}
            and "model" in event.get("payload", {})
        }
    )

    return RunRecord(
        run_id=run_id,
        started_at=(run_started or first_event)["timestamp"],
        ended_at=ended_at,
        status=status,
        task_summary=(run_started or {}).get("payload", {}).get("task_summary", ""),
        models_used=models_used,
        event_count=len(events),
        invalid_count=invalid_count,
        outcome=outcome,
    )


def write_run_record(run_dir: Path) -> Path:
    record = build_run_record(run_dir)
    path = Path(run_dir) / "run.json"
    path.write_text(record.model_dump_json() + "\n", encoding="utf-8")
    return path


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _line_count(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
