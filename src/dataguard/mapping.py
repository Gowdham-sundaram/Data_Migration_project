from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from .config import MappingConfig


def load_mapping_config(path: str | Path) -> list[MappingConfig]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    mappings = data.get("mappings", data)
    return [MappingConfig.model_validate(item) for item in mappings]


def _cast_value(value: Any, cast: str) -> Any:
    if pd.isna(value) or (isinstance(value, str) and not value.strip()):
        return value
    if cast == "str":
        return str(value)
    if cast == "int":
        number = float(value)
        if not number.is_integer():
            raise ValueError("invalid_integer")
        return int(number)
    if cast == "float":
        return float(value)
    if cast == "date":
        parsed = pd.to_datetime(value, format="mixed", errors="raise")
        return parsed.strftime("%Y-%m-%d")
    raise ValueError("unsupported_type_cast")


def transform_dataframe(
    frame: pd.DataFrame,
    mappings: list[MappingConfig],
) -> tuple[pd.DataFrame, list[dict[str, Any]], dict[str, int]]:
    target = pd.DataFrame(index=frame.index)
    issues: list[dict[str, Any]] = []
    change_counts: dict[str, int] = {}
    record_ids = [f"record-{position + 1:06d}" for position in range(len(frame))]

    target_names = [mapping.target_field for mapping in mappings]
    if len(target_names) != len(set(target_names)):
        raise ValueError("Mapping configuration has duplicate target fields.")

    supported_transforms = {None, "trim", "lower", "upper"}
    supported_casts = {None, "str", "int", "float", "date"}
    for mapping in mappings:
        if mapping.transform not in supported_transforms:
            raise ValueError(f"Unsupported transform configured for field '{mapping.target_field}'.")
        if mapping.type_cast not in supported_casts:
            raise ValueError(f"Unsupported type cast configured for field '{mapping.target_field}'.")
        if mapping.source_field not in frame.columns and mapping.default_value is None:
            if mapping.required:
                for row_position, record_id in enumerate(record_ids):
                    issues.append({
                        "record_id": record_id,
                        "source_row": row_position + 2,
                        "field": mapping.target_field,
                        "category": "missing_source_field",
                        "rule_id": "mapping.required_source",
                    })
            target[mapping.target_field] = pd.Series([pd.NA] * len(frame), index=frame.index)
            continue

        if mapping.source_field in frame.columns:
            source_values = frame[mapping.source_field].tolist()
        else:
            source_values = [mapping.default_value] * len(frame)

        output_values: list[Any] = []
        for row_position, value in enumerate(source_values):
            record_id = record_ids[row_position]
            original = value
            missing_value = pd.isna(value) or (isinstance(value, str) and not value.strip())
            if missing_value and mapping.default_value is not None:
                value = mapping.default_value
                change_counts[f"{mapping.target_field}.defaulted"] = change_counts.get(f"{mapping.target_field}.defaulted", 0) + 1

            if isinstance(value, str):
                if mapping.transform in {"trim", "lower", "upper"}:
                    transformed = value.strip()
                    if mapping.transform == "lower":
                        transformed = transformed.lower()
                    elif mapping.transform == "upper":
                        transformed = transformed.upper()
                    if transformed != value:
                        change_counts[f"{mapping.target_field}.{mapping.transform}"] = change_counts.get(f"{mapping.target_field}.{mapping.transform}", 0) + 1
                    value = transformed

            if not pd.isna(value) and mapping.value_mapping:
                lookup = str(value)
                if lookup in mapping.value_mapping:
                    value = mapping.value_mapping[lookup]
                    change_counts[f"{mapping.target_field}.value_mapped"] = change_counts.get(f"{mapping.target_field}.value_mapped", 0) + 1
                else:
                    issues.append({
                        "record_id": record_id,
                        "source_row": row_position + 2,
                        "field": mapping.target_field,
                        "category": "unmapped_code",
                        "rule_id": "mapping.value_mapping",
                    })

            if mapping.type_cast and not pd.isna(value) and str(value).strip():
                try:
                    casted = _cast_value(value, mapping.type_cast)
                    if casted != value:
                        change_counts[f"{mapping.target_field}.cast_{mapping.type_cast}"] = change_counts.get(f"{mapping.target_field}.cast_{mapping.type_cast}", 0) + 1
                    value = casted
                except (TypeError, ValueError, OverflowError):
                    issues.append({
                        "record_id": record_id,
                        "source_row": row_position + 2,
                        "field": mapping.target_field,
                        "category": "invalid_type_conversion",
                        "rule_id": f"mapping.cast_{mapping.type_cast}",
                    })
                    value = original

            if mapping.allowed_values is not None and not pd.isna(value) and str(value) not in mapping.allowed_values:
                issues.append({
                    "record_id": record_id,
                    "source_row": row_position + 2,
                    "field": mapping.target_field,
                    "category": "value_not_allowed",
                    "rule_id": "mapping.allowed_values",
                })
            output_values.append(value)
        target[mapping.target_field] = output_values
    return target, issues, change_counts


def apply_mapping(frame: pd.DataFrame, mappings: list[MappingConfig]) -> pd.DataFrame:
    target, issues, _ = transform_dataframe(frame, mappings)
    if issues:
        categories = sorted({str(issue["category"]) for issue in issues})
        raise ValueError(
            f"Mapping produced {len(issues)} exception(s) in categories: {', '.join(categories)}. "
            "Use transform_dataframe to review exception details."
        )
    return target
