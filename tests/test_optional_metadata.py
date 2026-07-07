from harness_core.replay import render_timeline
from harness_core.run_writer import RunWriter
from harness_core.validation import validate_event


OPTIONAL_METADATA = {
    "reasoning_level": "high",
    "context_window": 128000,
    "context_window_used": 42000,
    "context_packet_id": "ctx-001",
    "context_refs": ["plan-08", "run-abc12345"],
}


def test_model_call_started_accepts_optional_metadata() -> None:
    raw = {
        "run_id": "run-meta",
        "seq": 0,
        "timestamp": "2026-06-12T08:00:00Z",
        "event_type": "model_call_started",
        "agent": "agent",
        "payload": {"model": "m", **OPTIONAL_METADATA},
    }

    result = validate_event(raw, "run-meta", -1)

    assert result.ok


def test_model_call_completed_optional_metadata_absent_still_validates() -> None:
    raw = {
        "run_id": "run-meta",
        "seq": 0,
        "timestamp": "2026-06-12T08:00:00Z",
        "event_type": "model_call_completed",
        "agent": "agent",
        "payload": {
            "model": "m",
            "tokens_in": 1,
            "tokens_out": 2,
            "latency_ms": 3,
            "status": "ok",
        },
    }

    result = validate_event(raw, "run-meta", -1)

    assert result.ok


def test_replay_renders_model_events_with_optional_metadata(tmp_path) -> None:
    writer = RunWriter(tmp_path, "run-meta")
    writer.new_run("optional metadata")
    writer.append("model_call_started", "agent", {"model": "m", **OPTIONAL_METADATA})
    writer.append(
        "model_call_completed",
        "agent",
        {
            "model": "m",
            "tokens_in": 1,
            "tokens_out": 2,
            "latency_ms": 3,
            "status": "ok",
            **OPTIONAL_METADATA,
        },
    )

    timeline = render_timeline(tmp_path / "run-meta")

    assert "model_call_started" in timeline
    assert "model_call_completed" in timeline
    assert "SUMMARY" in timeline
