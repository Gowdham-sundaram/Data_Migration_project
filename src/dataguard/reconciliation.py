from __future__ import annotations

from typing import Any

import pandas as pd


def _normalize_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    if isinstance(value, str):
        return value.strip().lower()
    return value


def reconcile_records(
    source_df: pd.DataFrame,
    target_df: pd.DataFrame,
    source_key: str,
    target_key: str,
    field_mapping: dict[str, str] | None = None,
) -> dict[str, Any]:
    source_key_values = source_df[source_key].tolist()
    target_key_values = target_df[target_key].tolist()

    source_count = len(source_df)
    target_count = len(target_df)
    matched_count = 0
    missing_records: list[str] = []
    extra_records: list[str] = []
    mismatches: list[dict[str, Any]] = []
    null_keys = 0

    for index, row in source_df.iterrows():
        key_value = row.get(source_key)
        if pd.isna(key_value) or str(key_value).strip() == "":
            null_keys += 1
            continue

        target_match = target_df[target_df[target_key].astype(str).str.strip() == str(key_value).strip()]
        if target_match.empty:
            missing_records.append(str(key_value))
            continue

        matched_count += 1
        if field_mapping is not None:
            for source_field, target_field in field_mapping.items():
                source_value = row.get(source_field)
                target_value = target_match.iloc[0].get(target_field)
                if _normalize_value(source_value) != _normalize_value(target_value):
                    mismatches.append(
                        {
                            "source_key": str(key_value),
                            "source_field": source_field,
                            "target_field": target_field,
                            "source_value": str(source_value),
                            "target_value": str(target_value),
                        }
                    )

    for target_key_value in target_key_values:
        if pd.isna(target_key_value) or str(target_key_value).strip() == "":
            continue
        if str(target_key_value).strip() not in {str(v).strip() for v in source_key_values if str(v).strip() != ""}:
            extra_records.append(str(target_key_value))

    return {
        "source_count": source_count,
        "target_count": target_count,
        "matched_records": matched_count,
        "missing_records": len(missing_records),
        "extra_records": len(extra_records),
        "field_mismatches": len(mismatches),
        "null_keys": null_keys,
        "missing_identity_values": missing_records,
        "extra_identity_values": extra_records,
        "mismatches": mismatches,
    }
