from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from harness_core.run_record import build_run_record


def render_timeline(run_dir: Path) -> str:
    run_dir = Path(run_dir)
    events = _read_jsonl(run_dir / "events.jsonl")
    invalid_events = _read_jsonl(run_dir / "events.invalid.jsonl")

    lines = [f"RUN {run_dir.name}", ""]
    for event in events:
        lines.append(
            f"{event['seq']}  {event['timestamp']}  {event['agent']}  "
            f"{event['event_type']}  {_payload_digest(event)}"
        )

    if invalid_events:
        lines.extend(["", "INVALID"])
        for event in invalid_events:
            seq = event.get("seq", "?")
            timestamp = event.get("timestamp", "?")
            agent = event.get("agent", "?")
            event_type = event.get("event_type", "?")
            lines.append(f"{seq}  {timestamp}  {agent}  {event_type}  ERROR: {event.get('_error')}")

    record = build_run_record(run_dir)
    lines.extend(
        [
            "",
            f"SUMMARY status={record.status} events={record.event_count} "
            f"invalid={record.invalid_count} outcome={record.outcome}",
        ]
    )
    return "\n".join(lines) + "\n"


def _payload_digest(event: dict[str, Any]) -> str:
    payload = event.get("payload", {})
    event_type = event.get("event_type")

    if event_type == "run_started":
        return payload.get("task_summary", "")
    if event_type == "task_received":
        return payload.get("task", "")
    if event_type in {"model_call_started", "model_call_completed"}:
        status = f" status={payload['status']}" if "status" in payload else ""
        return f"model={payload.get('model', '')}{status}"
    if event_type in {"file_read", "file_edited"}:
        return f"path={payload.get('path', '')}"
    if event_type == "command_completed":
        return f"exit={payload.get('exit_code')} command={payload.get('command', '')}"
    if event_type == "validator_completed":
        return f"validator={payload.get('validator', '')} passed={payload.get('passed')}"
    if event_type == "decision_made":
        return (
            f"{payload.get('decision_type', '')} choice={payload.get('choice', '')} "
            f"confidence={payload.get('confidence')}"
        )
    if event_type == "human_override":
        return f"decision_ref={payload.get('decision_ref')} human_choice={payload.get('human_choice', '')}"
    if event_type == "approval_requested":
        return f"request_id={payload.get('request_id', '')}"
    if event_type == "approval_resolved":
        return f"request_id={payload.get('request_id', '')} outcome={payload.get('outcome', '')}"
    if event_type == "run_completed":
        return f"outcome={payload.get('outcome', '')}"
    if event_type == "run_failed":
        return f"error={payload.get('error', '')}"
    return json.dumps(payload, separators=(",", ":"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
