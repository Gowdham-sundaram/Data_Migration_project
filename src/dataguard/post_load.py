from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from .audit import generate_run_id
from .profiler import profile_dataframe
from .validation import ValidationResult, validate_dataframe


def _blank(value: Any) -> bool:
    return pd.isna(value) or (isinstance(value, str) and not value.strip())


def reconcile_loaded_data(
    source_df: pd.DataFrame,
    target_df: pd.DataFrame,
    source_key_fields: list[str],
    target_key_fields: list[str],
    field_mapping: dict[str, str],
) -> dict[str, Any]:
    if not source_key_fields or len(source_key_fields) != len(target_key_fields):
        raise ValueError("Provide the same non-zero number of source and target key fields.")
    missing_source = sorted((set(source_key_fields) | set(field_mapping)) - set(source_df.columns))
    if missing_source:
        raise ValueError("Configured source reconciliation fields are missing from the approved source export.")
    missing_target = sorted((set(target_key_fields) | set(field_mapping.values())) - set(target_df.columns))
    missing_target_keys = sorted(set(target_key_fields) - set(target_df.columns))
    missing_compare_fields = sorted(set(field_mapping.values()) - set(target_df.columns))
    exceptions: list[dict[str, str]] = []

    if missing_target_keys:
        exceptions = [
            {
                "stage": "reconciliation",
                "record_id": "target-dataset",
                "field": field_name,
                "category": "missing_target_key_field",
                "rule_id": "reconciliation.target_key_schema",
            }
            for field_name in missing_target_keys
        ]
        exceptions.extend(
            {
                "stage": "reconciliation",
                "record_id": "target-dataset",
                "field": field_name,
                "category": "missing_target_comparison_field",
                "rule_id": "reconciliation.field_schema",
            }
            for field_name in missing_compare_fields
        )
        return {
            "source_count": len(source_df),
            "target_count": len(target_df),
            "matched_key_count": 0,
            "missing_target_key_count": None,
            "extra_target_key_count": None,
            "source_null_key_rows": 0,
            "target_null_key_rows": 0,
            "source_duplicate_key_count": 0,
            "source_duplicate_key_rows": 0,
            "target_duplicate_key_count": 0,
            "target_duplicate_key_rows": 0,
            "compared_record_count": 0,
            "exact_match_count": 0,
            "normalized_match_count": 0,
            "field_mismatch_count": 0,
            "field_mismatch_counts": {},
            "mismatch_examples": [],
            "exceptions": exceptions,
            "comparison_truncated": False,
            "missing_target_key_fields_count": len(missing_target_keys),
            "status": "issues_found",
        }

    exceptions.extend(
        {
            "stage": "reconciliation",
            "record_id": "target-dataset",
            "field": field_name,
            "category": "missing_target_comparison_field",
            "rule_id": "reconciliation.field_schema",
        }
        for field_name in missing_compare_fields
    )

    def index_records(frame: pd.DataFrame, keys: list[str]) -> tuple[dict[tuple[str, ...], list[int]], int]:
        index: dict[tuple[str, ...], list[int]] = {}
        null_key_rows = 0
        for row_position, (_, row) in enumerate(frame.iterrows()):
            key = tuple(str(row[field]).strip() for field in keys)
            if any(_blank(row[field]) for field in keys):
                null_key_rows += 1
                continue
            index.setdefault(key, []).append(row_position)
        return index, null_key_rows

    source_index, source_null_keys = index_records(source_df, source_key_fields)
    target_index, target_null_keys = index_records(target_df, target_key_fields)
    source_duplicate_rows = sum(len(positions) for positions in source_index.values() if len(positions) > 1)
    target_duplicate_rows = sum(len(positions) for positions in target_index.values() if len(positions) > 1)
    source_keys = set(source_index)
    target_keys = set(target_index)
    common_keys = source_keys & target_keys

    for key, positions in source_index.items():
        if len(positions) > 1:
            for position in positions:
                exceptions.append({
                    "stage": "reconciliation",
                    "record_id": f"source-record-{position + 1:06d}",
                    "field": "+".join(source_key_fields),
                    "category": "duplicate_source_key",
                    "rule_id": "reconciliation.unique_source_key",
                })
    for key, positions in target_index.items():
        if len(positions) > 1:
            for position in positions:
                exceptions.append({
                    "stage": "reconciliation",
                    "record_id": f"target-record-{position + 1:06d}",
                    "field": "+".join(target_key_fields),
                    "category": "duplicate_target_key",
                    "rule_id": "reconciliation.unique_target_key",
                })
    for position, (_, row) in enumerate(source_df.iterrows()):
        if any(_blank(row[field]) for field in source_key_fields):
            exceptions.append({
                "stage": "reconciliation",
                "record_id": f"source-record-{position + 1:06d}",
                "field": "+".join(source_key_fields),
                "category": "null_source_key",
                "rule_id": "reconciliation.business_key_required",
            })
    for position, (_, row) in enumerate(target_df.iterrows()):
        if any(_blank(row[field]) for field in target_key_fields):
            exceptions.append({
                "stage": "reconciliation",
                "record_id": f"target-record-{position + 1:06d}",
                "field": "+".join(target_key_fields),
                "category": "null_target_key",
                "rule_id": "reconciliation.business_key_required",
            })
    for key in sorted(source_keys - target_keys):
        for position in source_index[key]:
            exceptions.append({
                "stage": "reconciliation",
                "record_id": f"source-record-{position + 1:06d}",
                "field": "+".join(source_key_fields),
                "category": "missing_target_record",
                "rule_id": "reconciliation.target_presence",
            })
    for key in sorted(target_keys - source_keys):
        for position in target_index[key]:
            exceptions.append({
                "stage": "reconciliation",
                "record_id": f"target-record-{position + 1:06d}",
                "field": "+".join(target_key_fields),
                "category": "extra_target_record",
                "rule_id": "reconciliation.source_presence",
            })

    mismatch_counts = {
        f"{source_field}->{target_field}": 0
        for source_field, target_field in field_mapping.items()
        if target_field not in missing_target
    }
    mismatch_examples: list[dict[str, Any]] = []
    exact_match_rows = 0
    normalized_match_rows = 0
    compared_records = 0
    for key in sorted(common_keys):
        source_row_position = source_index[key][0]
        target_row_position = target_index[key][0]
        source_row = source_df.iloc[source_row_position]
        target_row = target_df.iloc[target_row_position]
        exact_record_match = True
        record_mismatch_count = 0
        for source_field, target_field in field_mapping.items():
            source_value = source_row[source_field]
            target_value = target_row[target_field]
            if _blank(source_value) and _blank(target_value):
                continue
            exact = str(source_value) == str(target_value)
            normalized = str(source_value).strip().casefold() == str(target_value).strip().casefold()
            if not normalized:
                record_mismatch_count += 1
                exact_record_match = False
                mismatch_key = f"{source_field}->{target_field}"
                mismatch_counts[mismatch_key] += 1
                if len(mismatch_examples) < 100:
                    mismatch_examples.append({
                        "record_id": f"source-record-{source_row_position + 1:06d}",
                        "field_mapping": mismatch_key,
                        "category": "field_mismatch",
                    })
                    exceptions.append({
                        "stage": "reconciliation",
                        "record_id": f"source-record-{source_row_position + 1:06d}",
                        "field": mismatch_key,
                        "category": "field_mismatch",
                        "rule_id": "reconciliation.field_compare",
                    })
            elif not exact:
                exact_record_match = False
        compared_records += 1
        if record_mismatch_count == 0:
            if exact_record_match:
                exact_match_rows += 1
            else:
                normalized_match_rows += 1

    source_duplicate_keys = sum(1 for positions in source_index.values() if len(positions) > 1)
    target_duplicate_keys = sum(1 for positions in target_index.values() if len(positions) > 1)
    return {
        "source_count": len(source_df),
        "target_count": len(target_df),
        "matched_key_count": len(common_keys),
        "missing_target_key_count": len(source_keys - target_keys),
        "extra_target_key_count": len(target_keys - source_keys),
        "source_null_key_rows": source_null_keys,
        "target_null_key_rows": target_null_keys,
        "source_duplicate_key_count": source_duplicate_keys,
        "source_duplicate_key_rows": source_duplicate_rows,
        "target_duplicate_key_count": target_duplicate_keys,
        "target_duplicate_key_rows": target_duplicate_rows,
        "compared_record_count": compared_records,
        "exact_match_count": exact_match_rows,
        "normalized_match_count": normalized_match_rows,
        "field_mismatch_count": sum(mismatch_counts.values()),
        "field_mismatch_counts": mismatch_counts,
        "mismatch_examples": mismatch_examples,
        "exceptions": exceptions,
        "comparison_truncated": sum(mismatch_counts.values()) > len(mismatch_examples),
        "status": "passed" if not (
            source_keys - target_keys
            or target_keys - source_keys
            or source_null_keys
            or target_null_keys
            or source_duplicate_keys
            or target_duplicate_keys
            or sum(mismatch_counts.values())
        ) else "issues_found",
    }


def build_post_load_exceptions(
    validation: ValidationResult,
    reconciliation: dict[str, Any],
) -> list[dict[str, Any]]:
    exceptions: list[dict[str, Any]] = []
    for issue in validation.issues:
        exceptions.append({
            "stage": "target_validation",
            "record_id": f"target-{issue.record_id}" if issue.record_id else "target-dataset",
            "field": issue.field,
            "category": issue.code,
            "rule_id": issue.code,
        })
    exceptions.extend(reconciliation["exceptions"])
    return exceptions


def write_post_load_reports(
    target_df: pd.DataFrame,
    validation: ValidationResult,
    reconciliation: dict[str, Any],
    output_dir: str | Path,
    overwrite: bool = False,
    config_version: str = "unspecified",
) -> dict[str, Any]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    run_id = generate_run_id("postload")
    exceptions = build_post_load_exceptions(validation, reconciliation)

    profile = profile_dataframe(target_df)
    profile_rows = [
        {
            "field": field_name,
            "inferred_type": metrics["inferred_type"],
            "null_count": metrics["null_count"],
            "blank_count": metrics["blank_count"],
            "distinct_count": metrics["distinct_count"],
            "duplicate_value_rows": metrics["duplicate_value_rows"],
            "numeric_min": (metrics["numeric_range"] or {}).get("min"),
            "numeric_max": (metrics["numeric_range"] or {}).get("max"),
            "potential_numeric_outlier_count": metrics["potential_numeric_outlier_count"],
            "format_issue_count": len(metrics["format_issues"]),
        }
        for field_name, metrics in profile["column_metrics"].items()
    ]
    issue_counts: dict[str, int] = {}
    for issue in validation.issues:
        issue_counts[issue.code] = issue_counts.get(issue.code, 0) + 1
    for exception in reconciliation["exceptions"]:
        category = str(exception["category"])
        issue_counts[category] = issue_counts.get(category, 0) + 1

    summary: dict[str, Any] = {
        "run_id": run_id,
        "run_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "config_version": config_version,
        "status": "passed" if validation.valid and reconciliation["status"] == "passed" else "issues_found",
        "reconciliation_status": reconciliation["status"],
        "source_count": reconciliation["source_count"],
        "target_count": reconciliation["target_count"],
        "target_validation_valid": int(validation.valid),
        "target_validation_issue_count": len(validation.issues),
        **{
            key: value
            for key, value in reconciliation.items()
            if key not in {"field_mismatch_counts", "mismatch_examples", "exceptions", "status"}
        },
    }
    report_frames = {
        "post_load_summary.csv": pd.DataFrame([summary]),
        "target_profile.csv": pd.DataFrame(profile_rows),
        "post_load_exceptions.csv": pd.DataFrame(
            exceptions,
            columns=["stage", "record_id", "field", "category", "rule_id"],
        ),
        "post_load_exception_counts.csv": pd.DataFrame(
            [{"category": category, "count": count} for category, count in sorted(issue_counts.items())],
            columns=["category", "count"],
        ),
        "post_load_field_mismatches.csv": pd.DataFrame(
            [
                {"field_mapping": field_mapping, "mismatch_count": count}
                for field_mapping, count in sorted(reconciliation["field_mismatch_counts"].items())
            ],
            columns=["field_mapping", "mismatch_count"],
        ),
    }

    final_paths = {name: output_path / name for name in report_frames}
    existing = [path.name for path in final_paths.values() if path.exists()]
    if existing and not overwrite:
        raise FileExistsError(f"Refusing to overwrite existing post-load report: {existing[0]}")

    staged_paths: dict[str, Path] = {}
    reserved_paths: set[Path] = set()
    published_paths: set[Path] = set()
    try:
        for name, frame in report_frames.items():
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="",
                suffix=".csv",
                dir=output_path,
                delete=False,
            ) as temp_file:
                staged_paths[name] = Path(temp_file.name)
            frame.to_csv(staged_paths[name], index=False)
        if not overwrite:
            for final_path in final_paths.values():
                with final_path.open("xb"):
                    pass
                reserved_paths.add(final_path)
        for name, final_path in final_paths.items():
            os.replace(staged_paths[name], final_path)
            published_paths.add(final_path)
    finally:
        for staged_path in staged_paths.values():
            staged_path.unlink(missing_ok=True)
        for reserved_path in reserved_paths - published_paths:
            reserved_path.unlink(missing_ok=True)

    return {
        "run_id": run_id,
        "summary": summary,
        "report_files": list(final_paths),
        "exception_count": len(exceptions),
    }
