import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from harness_core.run_record import RunRecord, build_run_record


FIXTURES = Path(__file__).parents[1] / "fixtures"


def test_success_run_record() -> None:
    record = build_run_record(FIXTURES / "runs" / "run-success")

    assert record.status == "completed"
    assert record.outcome == "success"
    assert record.event_count == 9
    assert record.invalid_count == 0
    assert record.models_used == ["nemotron-ultra"]


def test_failed_retry_run_record() -> None:
    record = build_run_record(FIXTURES / "runs" / "run-failed-retry")

    assert record.status == "failed"
    assert record.ended_at is not None
    assert record.outcome is None
    assert record.models_used == ["claude-sonnet", "nemotron-ultra"]


def test_run_completed_without_outcome_key_yields_none(tmp_path) -> None:
    events = [
        {
            "run_id": "run-x",
            "seq": 0,
            "timestamp": "2026-07-13T00:00:00Z",
            "event_type": "run_started",
            "agent": "orchestrator",
            "payload": {"task_summary": "x"},
        },
        {
            "run_id": "run-x",
            "seq": 1,
            "timestamp": "2026-07-13T00:00:01Z",
            "event_type": "run_completed",
            "agent": "orchestrator",
            "payload": {},
        },
    ]
    run_dir = tmp_path / "run-x"
    run_dir.mkdir()
    (run_dir / "events.jsonl").write_text(
        "".join(json.dumps(event) + "\n" for event in events), encoding="utf-8"
    )

    record = build_run_record(run_dir)

    assert record.status == "completed"
    assert record.outcome is None


def test_invalid_run_record_status_rejected() -> None:
    raw = json.loads((FIXTURES / "records" / "run.invalid.json").read_text())

    with pytest.raises(ValidationError):
        RunRecord(**raw)
