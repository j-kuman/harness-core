from pathlib import Path

from harness_core.replay import render_timeline
from harness_core.run_writer import RunWriter


FIXTURES = Path(__file__).parents[1] / "fixtures"


def test_replay_shows_decision_override_linkage() -> None:
    output = render_timeline(FIXTURES / "runs" / "run-decision-override")

    assert "decision_made" in output
    assert "human_override" in output
    assert "decision_ref=4" in output


def test_replay_shows_invalid_section(tmp_path) -> None:
    source = FIXTURES / "runs" / "run-invalid-events" / "events.jsonl"
    writer = RunWriter(tmp_path, "run-invalid-events")
    for line in source.read_text().splitlines():
        import json

        writer.append_raw(json.loads(line))

    output = render_timeline(tmp_path / "run-invalid-events")

    assert "events=6 invalid=3" in output
    assert "INVALID" in output
    assert output.count("ERROR:") == 3
