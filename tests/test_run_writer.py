import json

from harness_core.run_writer import RunWriter


def test_new_run_and_valid_appends_write_monotonic_events(tmp_path) -> None:
    writer = RunWriter(tmp_path, "run-test")

    run_id = writer.new_run("x")
    writer.append("task_received", "orchestrator", {"task": "x"})
    writer.append("file_read", "cline-implementer", {"path": "src/app.py"})
    writer.append("run_completed", "orchestrator", {"outcome": "success"})

    lines = (tmp_path / run_id / "events.jsonl").read_text().splitlines()
    records = [json.loads(line) for line in lines]

    assert [record["seq"] for record in records] == [0, 1, 2, 3]
    assert not (tmp_path / run_id / "events.invalid.jsonl").exists()


def test_reopen_tolerates_torn_tail_line(tmp_path) -> None:
    writer = RunWriter(tmp_path, "run-torn")
    writer.new_run("x")
    writer.append("task_received", "orchestrator", {"task": "x"})

    events_path = tmp_path / "run-torn" / "events.jsonl"
    with events_path.open("a", encoding="utf-8") as handle:
        handle.write('{"run_id":"run-torn","seq":2,"timestamp":"2026-')

    reopened = RunWriter(tmp_path, "run-torn")

    assert reopened.prev_seq == 1
    assert reopened.append("run_completed", "orchestrator", {"outcome": "success"}) == 2
    # The torn line stays on disk as forensic evidence for readers.
    assert '{"run_id":"run-torn","seq":2,"timestamp":"2026-' in events_path.read_text(encoding="utf-8")


def test_reopen_tolerates_line_without_valid_seq(tmp_path) -> None:
    writer = RunWriter(tmp_path, "run-noseq")
    writer.new_run("x")

    events_path = tmp_path / "run-noseq" / "events.jsonl"
    with events_path.open("a", encoding="utf-8") as handle:
        handle.write('{"run_id":"run-noseq","event_type":"task_received"}\n')
        handle.write('{"run_id":"run-noseq","seq":true}\n')

    reopened = RunWriter(tmp_path, "run-noseq")

    assert reopened.prev_seq == 0


def test_invalid_append_quarantines_and_does_not_advance_seq(tmp_path) -> None:
    writer = RunWriter(tmp_path, "run-test")
    writer.new_run("x")

    bad_seq = writer.append("model_call_completed", "x", {"model": "m", "tokens_in": 1})
    good_seq = writer.append(
        "model_call_completed",
        "x",
        {"model": "m", "tokens_in": 1, "tokens_out": 2, "latency_ms": 3, "status": "ok"},
    )

    valid_records = [
        json.loads(line)
        for line in (tmp_path / "run-test" / "events.jsonl").read_text().splitlines()
    ]
    invalid_records = [
        json.loads(line)
        for line in (tmp_path / "run-test" / "events.invalid.jsonl").read_text().splitlines()
    ]

    assert bad_seq == -1
    assert good_seq == 1
    assert [record["seq"] for record in valid_records] == [0, 1]
    assert invalid_records[0]["_error"] == "medium payload contract failure: 3 issues"
    assert "missing required payload key: tokens_out" in invalid_records[0]["_errors"]
    assert invalid_records[0]["_summary"] == "medium payload contract failure: 3 issues"
    assert invalid_records[0]["_primary_failure_class"] == "payload_contract"
    assert invalid_records[0]["_severity"] == "medium"
    assert any(issue["code"] == "missing_payload_key" for issue in invalid_records[0]["_issues"])
