from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from .config import RuleConfig


@dataclass
class ValidationIssue:
    field: str
    row_index: int
    code: str
    message: str
    record_id: str | None = None


@dataclass
class ValidationResult:
    valid: bool
    issues: list[ValidationIssue] = field(default_factory=list)
    row_count: int = 0


def _rule_dict(rule: RuleConfig | dict[str, Any]) -> dict[str, Any]:
    if isinstance(rule, RuleConfig):
        values = rule.model_dump()
        values["required"] = rule.required
        return values
    return rule


def _matches_type(value: Any, expected: str) -> bool:
    text = str(value).strip()
    if expected in {"string", "str"}:
        return isinstance(value, str)
    if expected in {"integer", "int"}:
        try:
            return float(text).is_integer()
        except (TypeError, ValueError, OverflowError):
            return False
    if expected in {"number", "numeric", "float"}:
        try:
            float(text)
            return True
        except (TypeError, ValueError, OverflowError):
            return False
    if expected in {"date", "datetime"}:
        try:
            pd.to_datetime(text, format="mixed", errors="raise")
            return True
        except (TypeError, ValueError, OverflowError):
            return False
    if expected in {"boolean", "bool"}:
        return text.lower() in {"true", "false", "0", "1", "yes", "no"}
    raise ValueError(f"Unsupported validation data type: {expected}")


def validate_dataframe(
    frame: pd.DataFrame,
    rules: list[RuleConfig | dict[str, Any]],
    expected_columns: list[str] | None = None,
) -> ValidationResult:
    frame = frame.reset_index(drop=True)
    issues: list[ValidationIssue] = []
    normalized_rules = [_rule_dict(rule) for rule in rules]
    active_rules = [rule for rule in normalized_rules if rule.get("enabled", True)]

    if frame.empty:
        issues.append(ValidationIssue("*", -1, "empty_dataset", "Dataset contains no records"))

    if expected_columns is not None:
        for field_name in sorted(set(expected_columns) - set(frame.columns)):
            issues.append(ValidationIssue(field_name, -1, "missing_column", "Configured field is missing"))
        for field_name in sorted(set(frame.columns) - set(expected_columns)):
            issues.append(ValidationIssue(field_name, -1, "unexpected_column", "Field is not in the configured schema"))

    for rule in active_rules:
        field_name = rule.get("field")
        if not field_name:
            raise ValueError("Every validation rule must define a field.")
        if field_name not in frame.columns:
            issues.append(ValidationIssue(field_name, -1, "missing_column", "Configured field is missing"))
        if rule.get("regex") is not None:
            re.compile(str(rule["regex"]))
        if rule.get("data_type") not in {None, "string", "str", "integer", "int", "number", "numeric", "float", "date", "datetime", "boolean", "bool"}:
            raise ValueError(f"Unsupported validation data type for field '{field_name}'.")

    usable_rules = [rule for rule in active_rules if rule["field"] in frame.columns]
    for row_position, (_, row) in enumerate(frame.iterrows()):
        record_id = f"record-{row_position + 1:06d}"
        for rule in usable_rules:
            field_name = rule["field"]
            value = row[field_name]
            missing = pd.isna(value) or (isinstance(value, str) and not value.strip())
            if missing:
                if rule.get("required"):
                    issues.append(ValidationIssue(field_name, row_position, "missing_required", "Required value is missing", record_id))
                continue

            expected_type = rule.get("data_type")
            if expected_type and not _matches_type(value, str(expected_type)):
                issues.append(ValidationIssue(field_name, row_position, "invalid_type", "Value does not match configured type", record_id))

            try:
                numeric_value = float(value)
            except (TypeError, ValueError, OverflowError):
                numeric_value = None
            if numeric_value is not None:
                if rule.get("min_value") is not None and numeric_value < float(rule["min_value"]):
                    issues.append(ValidationIssue(field_name, row_position, "below_min", "Value is below configured minimum", record_id))
                if rule.get("max_value") is not None and numeric_value > float(rule["max_value"]):
                    issues.append(ValidationIssue(field_name, row_position, "above_max", "Value exceeds configured maximum", record_id))

            allowed = rule.get("allowed_values")
            if allowed is not None and str(value) not in {str(item) for item in allowed}:
                issues.append(ValidationIssue(field_name, row_position, "not_allowed", "Value is not in configured allowed values", record_id))

            pattern = rule.get("regex")
            if pattern is not None and re.fullmatch(str(pattern), str(value)) is None:
                issues.append(ValidationIssue(field_name, row_position, "format_mismatch", "Value does not match configured format", record_id))

            date_format = rule.get("date_format")
            if date_format is not None:
                try:
                    pd.to_datetime(value, format=date_format, errors="raise")
                except (TypeError, ValueError, OverflowError):
                    issues.append(ValidationIssue(field_name, row_position, "invalid_date", "Value does not match configured date format", record_id))

            other_field = rule.get("equals_field")
            if other_field:
                if other_field not in frame.columns:
                    raise ValueError(f"Cross-field rule references unknown field '{other_field}'.")
                other_value = row[other_field]
                if not pd.isna(other_value) and str(value) != str(other_value):
                    issues.append(ValidationIssue(field_name, row_position, "cross_field_mismatch", "Value does not match configured related field", record_id))

    for rule in usable_rules:
        if not rule.get("unique"):
            continue
        field_name = rule["field"]
        valid_values = frame[field_name][
            frame[field_name].notna()
            & ~frame[field_name].map(lambda value: isinstance(value, str) and not value.strip())
        ]
        duplicate_mask = valid_values.astype(str).str.strip().duplicated(keep=False)
        for position in duplicate_mask[duplicate_mask].index:
            issues.append(ValidationIssue(
                field_name,
                int(position),
                "duplicate_key",
                "Value is not unique",
                f"record-{int(position) + 1:06d}",
            ))

    return ValidationResult(valid=not issues, issues=issues, row_count=len(frame.index))
