from __future__ import annotations

import pandas as pd


def normalize_text(value: object) -> object:
    if isinstance(value, str):
        return value.strip()
    return value


def normalize_date(value: object) -> object:
    if pd.isna(value):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return value
        try:
            parsed = pd.to_datetime(text, format="mixed", errors="raise")
        except (TypeError, ValueError):
            return value
        return parsed.strftime("%Y-%m-%d")
    return value


def clean_dataframe(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """Apply only the unambiguous whitespace-trimming operation."""
    cleaned = frame.copy()
    trimmed_count = 0
    for column in cleaned.columns:
        if cleaned[column].dtype == "object" or pd.api.types.is_string_dtype(cleaned[column].dtype):
            original = cleaned[column]
            cleaned[column] = original.map(normalize_text)
            trimmed_count += int(
                sum(
                    isinstance(before, str) and before != after
                    for before, after in zip(original.tolist(), cleaned[column].tolist())
                )
            )
    return cleaned, {"trimmed": trimmed_count}
