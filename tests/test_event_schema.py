import pytest
from pydantic import ValidationError

from harness_core.events import BaseEvent, EventType, REQUIRED_PAYLOAD_KEYS


def test_valid_event_constructs() -> None:
    event = BaseEvent(
        run_id="run-001",
        seq=3,
        timestamp="2026-06-11T14:03:22Z",
        event_type="model_call_completed",
        agent="orchestrator",
        payload={
            "model": "nemotron-ultra",
            "tokens_in": 1200,
            "tokens_out": 340,
            "latency_ms": 47200,
            "status": "ok",
        },
    )

    assert event.event_type is EventType.model_call_completed


def test_unknown_event_type_rejected() -> None:
    with pytest.raises(ValidationError):
        BaseEvent(
            run_id="run-001",
            seq=5,
            timestamp="2026-06-11T14:03:26Z",
            event_type="reviewer_started",
            agent="orchestrator",
            payload={},
        )


def test_required_payload_registry_has_model_completion_keys() -> None:
    keys = REQUIRED_PAYLOAD_KEYS[EventType.model_call_completed]

    assert {"tokens_in", "tokens_out", "latency_ms", "model", "status"} <= set(keys)


def test_required_payload_registry_covers_all_event_types() -> None:
    assert set(REQUIRED_PAYLOAD_KEYS) == set(EventType)
