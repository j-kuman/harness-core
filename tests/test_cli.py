from pathlib import Path

from typer.testing import CliRunner

from harness_core.cli import app


FIXTURES = Path(__file__).parents[1] / "fixtures"


def test_validate_success_fixture() -> None:
    result = CliRunner().invoke(app, ["validate", str(FIXTURES / "runs" / "run-success")])

    assert result.exit_code == 0
    assert "OK: 9 events" in result.output


def test_validate_invalid_fixture_exits_one() -> None:
    result = CliRunner().invoke(app, ["validate", str(FIXTURES / "runs" / "run-invalid-events")])

    assert result.exit_code == 1
    assert result.output.count("line ") == 3


def test_summary_failed_retry_writes_run_json(tmp_path) -> None:
    run_dir = tmp_path / "run-failed-retry"
    run_dir.mkdir()
    (run_dir / "events.jsonl").write_text(
        (FIXTURES / "runs" / "run-failed-retry" / "events.jsonl").read_text(),
        encoding="utf-8",
    )

    result = CliRunner().invoke(app, ["summary", str(run_dir)])

    assert result.exit_code == 0
    assert '"status":"failed"' in result.output
    assert (run_dir / "run.json").exists()


def test_quarantined_append_exits_two(tmp_path) -> None:
    runner = CliRunner()
    root = tmp_path / ".agent-runs"
    new_result = runner.invoke(app, ["new-run", "--task", "smoke", "--root", str(root)])
    run_id = new_result.output.strip()

    result = runner.invoke(
        app,
        [
            "append",
            run_id,
            "--type",
            "model_call_completed",
            "--agent",
            "x",
            "--payload",
            '{"model":"m","tokens_in":1}',
            "--root",
            str(root),
        ],
    )

    assert result.exit_code == 2
    assert "QUARANTINED:" in result.output
    assert "tokens_out" in result.output


def test_replay_command_outputs_timeline() -> None:
    result = CliRunner().invoke(app, ["replay", str(FIXTURES / "runs" / "run-decision-override")])

    assert result.exit_code == 0
    assert "decision_made" in result.output
    assert "human_override" in result.output
