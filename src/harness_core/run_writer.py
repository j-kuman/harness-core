from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from harness_core.validation import validate_event


class RunWriter:
    def __init__(self, root: Path, run_id: str | None = None) -> None:
        self.root = Path(root)
        self.run_id = run_id or f"run-{uuid.uuid4().hex[:8]}"
        self.run_dir = self.root / self.run_id
        self.prev_seq = self._read_prev_seq()

    def new_run(self, task_summary: str) -> str:
        self.run_dir.mkdir(parents=True, exist_ok=False)
        self.prev_seq = -1
        seq = self.append("run_started", "orchestrator", {"task_summary": task_summary})
        if seq != 0:
            raise RuntimeError("new run did not start at seq 0")
        return self.run_id

    def append(self, event_type: str, agent: str, payload: dict[str, Any]) -> int:
        raw = {
            "run_id": self.run_id,
            "seq": self.prev_seq + 1,
            "timestamp": _utc_now(),
            "event_type": event_type,
            "agent": agent,
            "payload": payload,
        }
        return self.append_raw(raw)

    def append_raw(self, raw: dict[str, Any]) -> int:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        result = validate_event(raw, self.run_id, self.prev_seq)
        if result.ok:
            self._append_jsonl(self.run_dir / "events.jsonl", raw)
            self.prev_seq = raw["seq"]
            return raw["seq"]

        quarantined = dict(raw)
        quarantined["_error"] = result.error
        quarantined["_errors"] = result.errors
        quarantined["_summary"] = result.summary
        quarantined["_primary_failure_class"] = result.primary_failure_class
        quarantined["_severity"] = result.severity
        quarantined["_issues"] = [issue.model_dump() for issue in result.issues]
        self._append_jsonl(self.run_dir / "events.invalid.jsonl", quarantined)
        return -1

    def _read_prev_seq(self) -> int:
        path = self.run_dir / "events.jsonl"
        if not path.exists():
            return -1

        prev_seq = -1
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                seq = json.loads(line)["seq"]
            except (json.JSONDecodeError, TypeError, KeyError):
                # A torn tail (crash mid-append) must not brick the writer;
                # the bad line stays on disk for readers to classify.
                continue
            if isinstance(seq, int) and not isinstance(seq, bool):
                prev_seq = max(prev_seq, seq)
        return prev_seq

    @staticmethod
    def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
        with path.open("a", encoding="utf-8", buffering=1) as handle:
            handle.write(json.dumps(record, separators=(",", ":")) + "\n")
            handle.flush()


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
