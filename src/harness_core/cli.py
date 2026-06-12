from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer

from harness_core.replay import render_timeline
from harness_core.run_record import write_run_record
from harness_core.run_writer import RunWriter
from harness_core.validation import validate_event_all

app = typer.Typer(no_args_is_help=True)


@app.command("new-run")
def new_run(task: str = typer.Option(..., "--task"), root: Path = typer.Option(Path(".agent-runs"), "--root")) -> None:
    writer = RunWriter(root)
    typer.echo(writer.new_run(task))


@app.command("append")
def append_event(
    run_id: str,
    event_type: str = typer.Option(..., "--type"),
    agent: str = typer.Option(..., "--agent"),
    payload: str = typer.Option(..., "--payload"),
    root: Path = typer.Option(Path(".agent-runs"), "--root"),
) -> None:
    try:
        parsed_payload = json.loads(payload)
    except json.JSONDecodeError as exc:
        typer.echo(f"Invalid payload JSON: {exc}", err=True)
        raise typer.Exit(2)
    if not isinstance(parsed_payload, dict):
        typer.echo("Invalid payload JSON: expected object", err=True)
        raise typer.Exit(2)

    writer = RunWriter(root, run_id)
    seq = writer.append(event_type, agent, parsed_payload)
    if seq == -1:
        record = _last_invalid_record(root / run_id)
        typer.echo(f"QUARANTINED: {record.get('_error', 'unknown error')}")
        for error in record.get("_errors", []):
            typer.echo(f"- {error}")
        raise typer.Exit(2)
    typer.echo(seq)


@app.command("validate")
def validate_run(run_dir: Path) -> None:
    valid_count, errors = _validate_run_lines(run_dir)
    if errors:
        for line_number, error in errors:
            typer.echo(f"line {line_number}: {error}")
        raise typer.Exit(1)
    typer.echo(f"OK: {valid_count} events")


@app.command("summary")
def summary(run_dir: Path) -> None:
    path = write_run_record(run_dir)
    typer.echo(path.read_text(encoding="utf-8").strip())


@app.command("replay")
def replay(run_dir: Path) -> None:
    typer.echo(render_timeline(run_dir), nl=False)


def _validate_run_lines(run_dir: Path) -> tuple[int, list[tuple[int, str]]]:
    path = run_dir / "events.jsonl"
    run_id = run_dir.name
    prev_seq = -1
    valid_count = 0
    errors: list[tuple[int, str]] = []

    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            raw: dict[str, Any] = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append((line_number, f"invalid json: {exc}"))
            continue
        result = validate_event_all(raw, run_id, prev_seq)
        if result.ok:
            prev_seq = raw["seq"]
            valid_count += 1
        else:
            for error in result.errors or [result.error or "invalid event"]:
                errors.append((line_number, error))

    return valid_count, errors


def _last_invalid_record(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "events.invalid.jsonl"
    if not path.exists():
        return {"_error": "unknown error"}
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        return {"_error": "unknown error"}
    return json.loads(lines[-1])
