# Hardening Pass — V1.0 task packet

_Created 2026-06-12. Spec owner: Opus. Implementer: Codex. Operator: Jeff._

## Session protocol (read this first, every session)

1. **Read current state before planning.** Run `git log --oneline -10` and re-read any file you intend to modify. Never plan or implement from conversational memory of the code — it has already drifted twice.
2. **Commit discipline.** `git commit -am "pre-codex: <task>"` before starting; `git commit -am "post-codex: <what changed>"` when done.
3. **Contract changes are recorded, never silent.** If a task forces a change to event schema, ValidationResult shape, file formats, or CLI exit codes, stop and flag it — those are locked contracts (see `HARNESS_CORE_IMPLEMENTATION_BRIEF.md` in the planning folder, amendments of 2026-06-12).
4. **Out of scope for Codex (reserved for Jeff's hand-edit, do not implement):** the `validate_event` dead-code wrapper collapse, the `error`/`summary` field dedupe, and the `"invalid payload value: seq"` message fix. Leave them alone even though they're obvious.

## Status

- ~~Structured ValidationIssue + severity/failure-class ranking~~ — **shipped** (see `validation.py`)
- ~~Quarantine forensics (`_error`, `_errors`, `_summary`, `_issues`, ...)~~ — **shipped** (see `run_writer.py`)
- Remaining: Tasks 0–2 below.

## Non-goals for this pass

- No RunLens (separate implementation brief coming).
- No trace ingestion/export layer (deferred until real run data exists).
- No new event types, no V1.5 deferred types, no SQLite, no FastAPI.

---

## Task 0 — One real dogfood trace (Jeff-led; Codex assists live)

Purpose: record an actual working session as a run, and find out whether the CLI is annoying before building more on it.

Behavior:
- Jeff starts a run (`harness new-run --task "validator cleanup hand-edit"`) and appends events as he does the (reserved) hand-edit session: `file_read`, `file_edited`, `command_completed` (pytest), `validator_completed`, `run_completed`.
- Codex's role: answer CLI questions, do NOT do the edit or emit the events for him.
- Friction observations go in `docs/cli-friction-notes.md` (bullet list, raw, no polish).

Acceptance criteria:
- A real run dir exists under `.agent-runs/` with ≥ 8 valid events including `run_started`, ≥1 `file_edited`, ≥1 `command_completed`, and a terminal event.
- `harness validate <run_dir>` exits 0.
- `harness replay <run_dir>` renders the timeline.
- `docs/cli-friction-notes.md` exists with at least 3 honest observations.

## Task 1 — `docs/event-contract.md` (in-repo contract doc)

Purpose: the repo is the shipping artifact and currently has no contract documentation; the implementation brief lives outside the repo.

Files: `docs/event-contract.md`.

Behavior: document, **derived from the code as it exists** (`events.py`, `validation.py`, `run_writer.py`, `run_record.py`):
- Base event fields and rules (`seq` is authoritative order; timestamps recorded, never used for ordering).
- All 14 `EventType` members with their required payload keys and value constraints.
- Deferred event types (rejected as unknown in V1).
- Quarantine semantics (`events.invalid.jsonl`, `_error`/`_errors`/`_issues` fields, seq not consumed by invalid events).
- ValidationResult shape incl. severity + failure-class taxonomy.
- `run.json` derivation rules.
- Statement that `payload` is open: extra keys are preserved and never rejected.

Acceptance criteria:
- Every member of the `EventType` enum appears in the doc.
- Every required payload key in `REQUIRED_PAYLOAD_KEYS` appears in the doc.
- Doc states the quarantine and seq-ordering rules.
- No contradiction with current code behavior (spot-check against tests).

## Task 2 — Optional metadata conventions (documented + regression-tested)

Purpose: pre-wire the joins downstream consumers (Context Caddy, dataset pipeline) will need, without any schema change.

Files: `docs/event-contract.md` (new section), `tests/test_optional_metadata.py`.

Behavior:
- Document reserved-but-optional payload keys for `model_call_started` / `model_call_completed`:
  - `reasoning_level` (string: `"none" | "low" | "medium" | "high"`)
  - `context_window` (int, model max)
  - `context_window_used` (int)
  - `context_packet_id` (string)
  - `context_refs` (list of strings)
- These are conventions only — the validator must NOT enforce them. No changes to `events.py` or `validation.py`.
- Tests prove openness: an event carrying all of these extras validates `ok=True`; replay renders it without error; a `model_call_completed` missing all of them still validates.

Acceptance criteria:
- `pytest tests/test_optional_metadata.py` passes.
- `git diff` shows zero changes to `src/harness_core/events.py` and `src/harness_core/validation.py`.
- Conventions section exists in `docs/event-contract.md`.

---

## After this pass

RunLens MVP is next, against its own implementation brief (Opus-authored, not yet written). Do not start it from this packet.
