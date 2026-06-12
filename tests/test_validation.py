import json
from pathlib import Path

from harness_core.validation import validate_event, validate_event_all


FIXTURES = Path(__file__).parents[1] / "fixtures"


def test_valid_event_passes() -> None:
    raw = {
        "run_id": "run-001",
        "seq": 3,
        "timestamp": "2026-06-11T14:03:22Z",
        "event_type": "model_call_completed",
        "agent": "orchestrator",
        "payload": {
            "model": "nemotron-ultra",
            "tokens_in": 1200,
            "tokens_out": 340,
            "latency_ms": 47200,
            "status": "ok",
        },
    }

    assert validate_event(raw, "run-001", 2).ok


def test_invalid_fixture_lines_return_expected_reasons() -> None:
    lines = [
        json.loads(line)
        for line in (FIXTURES / "runs" / "run-invalid-events" / "events.jsonl").read_text().splitlines()
    ]

    prev_seq = -1
    invalid_errors = []
    for raw in lines:
        result = validate_event(raw, "run-invalid-events", prev_seq)
        if result.ok:
            prev_seq = raw["seq"]
        else:
            invalid_errors.extend(result.errors)

    assert len(invalid_errors) == 3
    assert "unknown event_type: reviewer_started" in invalid_errors
    assert "missing required payload key: tokens_out" in invalid_errors
    assert "non-monotonic seq: 4 after 5" in invalid_errors


def test_decision_confidence_out_of_range_fails() -> None:
    raw = {
        "run_id": "run-001",
        "seq": 1,
        "timestamp": "2026-06-11T14:03:22Z",
        "event_type": "decision_made",
        "agent": "orchestrator",
        "payload": {
            "decision_type": "routing",
            "choice": "fast_model",
            "confidence": 1.4,
            "autonomy_level": "auto",
        },
    }

    result = validate_event(raw, "run-001", 0)

    assert not result.ok
    assert result.error is not None
    assert result.error == "medium payload contract failure: 1 issue"
    assert "invalid payload value: confidence" in result.errors
    assert result.primary_failure_class == "payload_contract"
    assert result.severity == "medium"


def test_missing_base_field_fails() -> None:
    result = validate_event({"run_id": "run-001"}, "run-001", -1)

    assert not result.ok
    assert result.error == "critical base schema failure: 5 issues"
    assert "missing base field: seq" in result.errors


def test_run_id_mismatch_fails() -> None:
    raw = {
        "run_id": "run-other",
        "seq": 0,
        "timestamp": "2026-06-11T14:03:22Z",
        "event_type": "run_started",
        "agent": "orchestrator",
        "payload": {"task_summary": "x"},
    }

    result = validate_event(raw, "run-001", -1)

    assert not result.ok
    assert result.error == "critical trace integrity failure: 1 issue"
    assert result.errors == ["run_id mismatch"]


def test_validate_event_all_collects_multiple_errors() -> None:
    raw = {
        "run_id": "wrong-run",
        "seq": 1,
        "timestamp": "2026-06-11T14:03:22Z",
        "event_type": "model_call_completed",
        "agent": "orchestrator",
        "payload": {
            "model": "nemotron-ultra",
            "tokens_in": -1,
            "latency_ms": 47200,
            "status": "bad",
        },
    }

    result = validate_event_all(raw, "run-001", 2)

    assert not result.ok
    assert "run_id mismatch" in result.errors
    assert "non-monotonic seq: 1 after 2" in result.errors
    assert "invalid payload value: tokens_in" in result.errors
    assert "missing required payload key: tokens_out" in result.errors
    assert "invalid payload value: status" in result.errors
    assert result.error == "critical trace integrity failure: 5 issues"
    assert result.primary_failure_class == "trace_integrity"
    assert result.severity == "critical"
    assert {issue.code for issue in result.issues} >= {
        "run_id_mismatch",
        "non_monotonic_seq",
        "invalid_payload_value",
        "missing_payload_key",
    }
