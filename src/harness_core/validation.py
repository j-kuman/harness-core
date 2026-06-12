from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ValidationError

from harness_core.events import BaseEvent, EventType, REQUIRED_PAYLOAD_KEYS


BASE_FIELDS = ("run_id", "seq", "timestamp", "event_type", "agent", "payload")
Severity = Literal["critical", "high", "medium", "low"]
FailureClass = Literal["base_schema", "trace_integrity", "event_contract", "payload_contract"]

SEVERITY_RANK: dict[str, int] = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
}

FAILURE_CLASS_RANK: dict[str, int] = {
    "base_schema": 0,
    "trace_integrity": 1,
    "event_contract": 2,
    "payload_contract": 3,
}


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


def validate_event(raw: dict[str, Any], expected_run_id: str, prev_seq: int) -> ValidationResult:
    result = validate_event_all(raw, expected_run_id, prev_seq)
    if result.ok:
        return result
    return result


def validate_event_all(raw: dict[str, Any], expected_run_id: str, prev_seq: int) -> ValidationResult:
    issues: list[ValidationIssue] = []

    for field in BASE_FIELDS:
        if field not in raw:
            issues.append(
                _issue(
                    "missing_base_field",
                    f"missing base field: {field}",
                    "base_schema",
                    "critical",
                    field,
                )
            )

    if issues:
        return _invalid_result(issues)

    try:
        event_type = EventType(raw["event_type"])
    except ValueError:
        issues.append(
            _issue(
                "unknown_event_type",
                f"unknown event_type: {raw['event_type']}",
                "event_contract",
                "critical",
                "event_type",
            )
        )
        event_type = None

    if raw["run_id"] != expected_run_id:
        issues.append(_issue("run_id_mismatch", "run_id mismatch", "trace_integrity", "critical", "run_id"))

    seq = raw["seq"]
    if not isinstance(seq, int):
        issues.append(_issue("invalid_base_value", "invalid payload value: seq", "base_schema", "high", "seq"))
    elif prev_seq >= 0 and seq <= prev_seq:
        issues.append(
            _issue(
                "non_monotonic_seq",
                f"non-monotonic seq: {seq} after {prev_seq}",
                "trace_integrity",
                "critical",
                "seq",
            )
        )

    payload = raw["payload"]
    if not isinstance(payload, dict):
        issues.append(_issue("invalid_payload_object", "invalid payload value: payload", "base_schema", "high", "payload"))
        payload = {}

    if event_type is not None:
        for key, spec in REQUIRED_PAYLOAD_KEYS[event_type].items():
            if key not in payload:
                issues.append(
                    _issue(
                        "missing_payload_key",
                        f"missing required payload key: {key}",
                        "payload_contract",
                        "medium",
                        key,
                    )
                )
            elif not _matches_spec(payload[key], spec):
                issues.append(
                    _issue(
                        "invalid_payload_value",
                        f"invalid payload value: {key}",
                        "payload_contract",
                        "medium",
                        key,
                    )
                )

    if event_type is not None:
        try:
            BaseEvent(**raw)
        except ValidationError as exc:
            for item in exc.errors():
                loc = ".".join(str(part) for part in item.get("loc", ())) or "event"
                message = f"invalid payload value: {loc}"
                if message not in [issue.message for issue in issues]:
                    issues.append(_issue("invalid_base_value", message, "base_schema", "high", loc))

    if issues:
        return _invalid_result(issues)

    return ValidationResult(ok=True, error=None, errors=[], summary=None, issues=[])


def _issue(
    code: str,
    message: str,
    failure_class: FailureClass,
    severity: Severity,
    field: str | None = None,
) -> ValidationIssue:
    return ValidationIssue(
        code=code,
        message=message,
        failure_class=failure_class,
        severity=severity,
        field=field,
    )


def _invalid_result(issues: list[ValidationIssue]) -> ValidationResult:
    ranked = sorted(
        issues,
        key=lambda issue: (SEVERITY_RANK[issue.severity], FAILURE_CLASS_RANK[issue.failure_class], issue.code),
    )
    primary = ranked[0]
    summary = _summarize_issues(issues)
    messages = [issue.message for issue in issues]
    return ValidationResult(
        ok=False,
        error=summary,
        errors=messages,
        summary=summary,
        primary_failure_class=primary.failure_class,
        severity=primary.severity,
        issues=issues,
    )


def _summarize_issues(issues: list[ValidationIssue]) -> str:
    critical_classes = {
        issue.failure_class for issue in issues if issue.severity == "critical"
    }
    high_classes = {
        issue.failure_class for issue in issues if issue.severity == "high"
    }
    if critical_classes:
        classes = critical_classes
        severity = "critical"
    elif high_classes:
        classes = high_classes
        severity = "high"
    else:
        classes = {issue.failure_class for issue in issues}
        severity = "medium"

    readable_classes = " + ".join(sorted(classes, key=lambda item: FAILURE_CLASS_RANK[item])).replace("_", " ")
    issue_count = len(issues)
    noun = "issue" if issue_count == 1 else "issues"
    return f"{severity} {readable_classes} failure: {issue_count} {noun}"


def _matches_spec(value: Any, spec: Any) -> bool:
    if spec is int:
        return isinstance(value, int) and not isinstance(value, bool)
    if spec is bool:
        return isinstance(value, bool)
    if spec is str:
        return isinstance(value, str)
    if spec is list:
        return isinstance(value, list)

    if isinstance(spec, tuple):
        kind = spec[0]
        if kind == "int_ge_0":
            return isinstance(value, int) and not isinstance(value, bool) and value >= 0
        if kind == "float_range":
            lower, upper = spec[1], spec[2]
            return isinstance(value, (int, float)) and not isinstance(value, bool) and lower <= float(value) <= upper
        if kind == "enum":
            allowed = spec[1]
            return value in allowed

    return False
