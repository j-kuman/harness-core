# Event contract

Harness Core records each run as an append-only event trace. A run lives under
`.agent-runs/<run_id>/` by default and stores valid events in `events.jsonl`.
The derived run summary is written to `run.json`.

This document describes the V1 contract implemented by `harness_core.events`,
`harness_core.validation`, `harness_core.run_writer`, and
`harness_core.run_record`.

## Event shape

Each line in `events.jsonl` is one JSON object with these required base fields:

| Field | Rule |
|---|---|
| `run_id` | Non-empty string. Must match the run directory name during validation. |
| `seq` | Integer greater than or equal to 0. This is the authoritative event order. |
| `timestamp` | Non-empty string. Writers emit UTC ISO-8601 timestamps ending in `Z`. |
| `event_type` | One of the 14 V1 `EventType` values listed below. |
| `agent` | Non-empty string naming the role or process that emitted the event. |
| `payload` | JSON object. Required keys depend on `event_type`. Extra keys are allowed and preserved. |

Ordering consumers must use `seq`, not `timestamp`. Timestamps are recorded for
inspection, but they are never the source of ordering truth.

## Payload contracts

The validator enforces required payload keys and value constraints. Payloads are
open: keys beyond the required contract are not rejected, and the writer
preserves them exactly in the JSONL record.

| Event type | Required payload |
|---|---|
| `run_started` | `task_summary`: string |
| `task_received` | `task`: string |
| `model_call_started` | `model`: string |
| `model_call_completed` | `model`: string; `tokens_in`: integer >= 0; `tokens_out`: integer >= 0; `latency_ms`: integer >= 0; `status`: `ok` or `error` |
| `file_read` | `path`: string |
| `file_edited` | `path`: string; `summary`: string |
| `command_completed` | `command`: string; `exit_code`: integer; `summary`: string |
| `validator_completed` | `validator`: string; `passed`: boolean; `errors`: list |
| `decision_made` | `decision_type`: string; `choice`: string; `confidence`: number from 0.0 through 1.0; `autonomy_level`: `auto`, `notify`, `review`, or `escalate` |
| `approval_requested` | `request_id`: string; `prompt`: string |
| `approval_resolved` | `request_id`: string; `outcome`: `granted` or `denied` |
| `human_override` | `decision_ref`: integer; `human_choice`: string; `reason`: string |
| `run_completed` | `outcome`: `success`, `partial`, or `failure` |
| `run_failed` | `error`: string |

The implementation uses strict integer checks for integer fields: booleans do
not count as integers. `confidence` accepts integers or floats within range, but
not booleans.

## Deferred events

These names are reserved for later milestones and are rejected as unknown event
types in V1:

- `context_loaded`
- `model_selected`
- `plan_created`
- `file_edit_intent`
- `command_intent`
- `validator_started`
- `reviewer_started`
- `reviewer_completed`
- `approval_granted`
- `approval_denied`
- `memory_write_requested`
- `memory_write_approved`
- `shadow_review`
- `policy_calibration_run`
- `autonomy_level_adjusted`

## Validation

`validate_event(raw, expected_run_id, prev_seq)` and `validate_event_all(...)`
return a `ValidationResult`.

```python
Severity = Literal["critical", "high", "medium", "low"]
FailureClass = Literal["base_schema", "trace_integrity", "event_contract", "payload_contract"]

class ValidationIssue(BaseModel):
    code: str
    message: str
    failure_class: FailureClass
    severity: Severity
    field: str | None = None

class ValidationResult(BaseModel):
    ok: bool
    error: str | None = None
    errors: list[str] = []
    summary: str | None = None
    primary_failure_class: FailureClass | None = None
    severity: Severity | None = None
    issues: list[ValidationIssue] = []
```

Missing base fields short-circuit because the event cannot be checked safely.
Otherwise validation collects all detectable issues:

- Missing base field: `base_schema`, `critical`
- Unknown `event_type`: `event_contract`, `critical`
- `run_id` mismatch: `trace_integrity`, `critical`
- Non-integer `seq`: `base_schema`, `high`
- Non-monotonic `seq`: `trace_integrity`, `critical`
- Non-object `payload`: `base_schema`, `high`
- Missing required payload key: `payload_contract`, `medium`
- Invalid required payload value: `payload_contract`, `medium`
- Pydantic base event construction errors: `base_schema`, `high`

`error` and `summary` hold the aggregate summary string. `errors` holds every
specific human-readable issue message. `primary_failure_class` and `severity`
come from the highest-ranked issue, using severity rank first and failure-class
rank second.

## Quarantine

`RunWriter.append(...)` and `RunWriter.append_raw(...)` validate before writing.
Valid events are appended to `events.jsonl`, and `prev_seq` advances to the
event's `seq`.

Invalid events are not dropped and do not crash the writer. They are appended to
`events.invalid.jsonl` in the same run directory with these forensic fields:

- `_error`: aggregate summary
- `_errors`: list of specific issue messages
- `_summary`: aggregate summary
- `_primary_failure_class`: highest-ranked failure class
- `_severity`: highest-ranked severity
- `_issues`: serialized `ValidationIssue` objects

Invalid events do not consume a sequence number. After a quarantined append, the
next valid append reuses the unconsumed `seq`.

## Run record

`build_run_record(run_dir)` derives a `RunRecord` from `events.jsonl` and, if it
exists, `events.invalid.jsonl`. `write_run_record(run_dir)` writes the model to
`run.json`.

| Field | Derivation |
|---|---|
| `run_id` | Run directory name. |
| `started_at` | Timestamp of the first `run_started` event, or the first valid event if no `run_started` exists. |
| `ended_at` | Timestamp of the last terminal event, or `null` if the run is still running. |
| `status` | `running` if no terminal event exists; `completed` for `run_completed`; `failed` for `run_failed`. |
| `task_summary` | `run_started.payload.task_summary`, or empty string if absent. |
| `models_used` | Sorted unique `model` values from `model_call_started` and `model_call_completed` events. |
| `event_count` | Count of valid events in `events.jsonl`. |
| `invalid_count` | Count of non-empty lines in `events.invalid.jsonl`, or 0 when absent. |
| `outcome` | `run_completed.payload.outcome` for completed runs, otherwise `null`. |

`RunRecord.status` is constrained to `running`, `completed`, or `failed`.
