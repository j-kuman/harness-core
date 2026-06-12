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


def test_invalid_run_record_status_rejected() -> None:
    raw = json.loads((FIXTURES / "records" / "run.invalid.json").read_text())

    with pytest.raises(ValidationError):
        RunRecord(**raw)
