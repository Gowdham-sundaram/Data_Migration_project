from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from .source_reader import read_csv_local


def _is_blank(value: object) -> bool:
    return isinstance(value, str) and not value.strip()


def _present_values(series: pd.Series) -> pd.Series:
    return series[series.notna() & ~series.map(_is_blank)].map(lambda value: str(value).strip())


def infer_column_type(series: pd.Series) -> str:
    values = _present_values(series)
    if values.empty:
        return "empty"
    numeric_values = pd.to_numeric(values, errors="coerce")
    if numeric_values.notna().all():
        return "numeric"
    if numeric_values.notna().any():
        return "mixed"
    date_like = values.str.contains(r"\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}", regex=True, na=False)
    if date_like.any():
        try:
            parsed = pd.to_datetime(values, format="mixed", errors="coerce")
            if parsed.notna().all() and date_like.all():
                return "date"
            return "mixed"
        except (TypeError, ValueError):
            return "mixed"
    return "string"


def _date_format_issues(values: pd.Series) -> list[str]:
    date_candidates = values[values.str.contains(r"\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}", regex=True, na=False)]
    if date_candidates.empty:
        return []
    parsed = pd.to_datetime(date_candidates, format="mixed", errors="coerce")
    if parsed.isna().any():
        return ["contains_invalid_date_values"]
    formats = set()
    for value in date_candidates:
        if "-" in value:
            formats.add("dash")
        elif "/" in value:
            formats.add("slash")
        elif "." in value:
            formats.add("dot")
    return ["inconsistent_date_formats"] if len(formats) > 1 else []


def profile_dataframe(
    frame: pd.DataFrame,
    candidate_keys: list[list[str]] | None = None,
) -> dict[str, Any]:
    metrics: dict[str, dict[str, Any]] = {}
    all_candidate_keys = candidate_keys or [[column] for column in frame.columns]
    duplicate_key_rows: dict[str, int] = {}
    missing_candidate_key_fields: dict[str, list[str]] = {}

    for key_fields in all_candidate_keys:
        missing_fields = [field for field in key_fields if field not in frame.columns]
        key_label = "+".join(key_fields)
        if missing_fields:
            duplicate_key_rows[key_label] = 0
            missing_candidate_key_fields[key_label] = missing_fields
            continue
        key_frame = frame[key_fields].copy()
        complete = key_frame.notna().all(axis=1)
        for field in key_fields:
            complete &= ~key_frame[field].map(_is_blank)
        duplicate_mask = key_frame.loc[complete].duplicated(keep=False)
        duplicate_key_rows[key_label] = int(duplicate_mask.sum())

    for column in frame.columns:
        series = frame[column]
        values = _present_values(series)
        numeric = pd.to_numeric(values, errors="coerce")
        numeric_range: dict[str, float] | None = None
        potential_outliers = 0
        if not values.empty and numeric.notna().all():
            numeric_range = {"min": float(numeric.min()), "max": float(numeric.max())}
            q1, q3 = numeric.quantile([0.25, 0.75])
            spread = q3 - q1
            if spread > 0:
                potential_outliers = int(((numeric < q1 - 1.5 * spread) | (numeric > q3 + 1.5 * spread)).sum())

        issues = _date_format_issues(values)
        if numeric.notna().any() and not numeric.notna().all():
            issues.append("contains_non_numeric_values")

        metrics[column] = {
            "inferred_type": infer_column_type(series),
            "null_count": int(series.isna().sum()),
            "blank_count": int(series.map(_is_blank).sum()),
            "distinct_count": int(series.nunique(dropna=True)),
            "duplicate_value_rows": int(values.duplicated(keep=False).sum()),
            "numeric_range": numeric_range,
            "potential_numeric_outlier_count": potential_outliers,
            "format_issues": issues,
        }

    return {
        "row_count": int(len(frame.index)),
        "column_count": int(len(frame.columns)),
        "columns": list(frame.columns),
        "column_metrics": metrics,
        "duplicate_candidate_key_rows": duplicate_key_rows,
        "missing_candidate_key_fields": missing_candidate_key_fields,
        "parse_warnings": [],
    }


def profile_csv(
    csv_path: str | Path,
    candidate_keys: list[list[str]] | None = None,
    encoding: str | None = None,
) -> dict[str, Any]:
    frame = read_csv_local(csv_path, encoding=encoding)
    result = profile_dataframe(frame, candidate_keys=candidate_keys)
    if len(frame.columns) == 0 and len(frame) == 0:
        result["parse_warnings"] = ["empty_file"]
    return result
