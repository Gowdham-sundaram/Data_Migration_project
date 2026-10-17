from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .cleaning import clean_dataframe
from .config import RuleConfig
from .exporter import write_preparation_outputs
from .mapping import load_mapping_config, transform_dataframe
from .profiler import profile_csv
from .post_load import reconcile_loaded_data, write_post_load_reports
from .reconciliation import reconcile_records
from .source_reader import read_csv_local
from .validation import validate_dataframe


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="data-migration-helper", description="Local data migration preparation and validation framework")
    subparsers = parser.add_subparsers(dest="command", required=True)

    profile_cmd = subparsers.add_parser("profile", help="Profile a source CSV file")
    profile_cmd.add_argument("--source", required=True, help="Path to the source CSV")
    profile_cmd.add_argument(
        "--key",
        action="append",
        default=[],
        help="Candidate key fields, comma-separated; repeat to profile multiple candidate keys",
    )

    validate_cmd = subparsers.add_parser("validate", help="Validate a dataset against configured rules")
    validate_cmd.add_argument("--source", required=True, help="Path to the dataset CSV")
    validate_cmd.add_argument("--config", required=True, help="JSON file containing validation rules")

    prepare_cmd = subparsers.add_parser("prepare", help="Prepare a clean export file and exception file")
    prepare_cmd.add_argument("--source", required=True, help="Path to the source CSV")
    prepare_cmd.add_argument("--mapping", required=True, help="Path to the mapping JSON config")
    prepare_cmd.add_argument("--output-dir", default="output", help="Destination folder for export artifacts")
    prepare_cmd.add_argument("--overwrite", action="store_true", help="Replace generated outputs when they already exist")

    reconcile_cmd = subparsers.add_parser("reconcile", help="Compare source and target records")
    reconcile_cmd.add_argument("--source", required=True)
    reconcile_cmd.add_argument("--target", required=True)
    reconcile_cmd.add_argument("--source-key", default="customer_id")
    reconcile_cmd.add_argument("--target-key", default="customer_key")

    post_load_cmd = subparsers.add_parser(
        "post-load",
        help="Validate a migrated target export and reconcile it against the approved source export",
    )
    post_load_cmd.add_argument("--source", required=True, help="Approved pre-load export CSV")
    post_load_cmd.add_argument("--target", required=True, help="Exported target data CSV")
    post_load_cmd.add_argument("--config", required=True, help="JSON schema/rules config used to validate target data")
    post_load_cmd.add_argument("--source-key", action="append", required=True, help="Source business key field; repeat for composite keys")
    post_load_cmd.add_argument("--target-key", action="append", required=True, help="Target business key field; repeat for composite keys")
    post_load_cmd.add_argument(
        "--field-map",
        action="append",
        default=[],
        help="Compared field pair in source=target form; repeat as needed (defaults to same-named configured fields)",
    )
    post_load_cmd.add_argument("--output-dir", required=True, help="Local folder for post-load reports")
    post_load_cmd.add_argument("--overwrite", action="store_true", help="Replace existing post-load reports")

    demo_cmd = subparsers.add_parser("run-demo", help="Run the synthetic demo workflow")
    demo_cmd.add_argument("--output-dir", default="reports/demo_aggregate")
    return parser


def _load_rules(config_path: str) -> list[RuleConfig]:
    config: dict[str, Any] = json.loads(Path(config_path).read_text(encoding="utf-8"))
    raw_rules = config.get("rules", [])
    return [RuleConfig.model_validate(rule) for rule in raw_rules]


def _profile_command(source: str, candidate_keys: list[str]) -> int:
    keys = [[field.strip() for field in key.split(",")] for key in candidate_keys]
    summary = profile_csv(source, candidate_keys=keys or None)
    print(json.dumps(summary, indent=2, default=str))
    return 0


def _validate_command(source: str, config_path: str) -> int:
    frame = read_csv_local(source)
    result = validate_dataframe(frame, _load_rules(config_path))
    print(json.dumps({
        "valid": result.valid,
        "row_count": result.row_count,
        "issue_count": len(result.issues),
        "issues": [issue.__dict__ for issue in result.issues],
    }, indent=2, default=str))
    return 0 if result.valid else 1


def _prepare_command(source: str, mapping: str, output_dir: str, overwrite: bool = False) -> int:
    frame = read_csv_local(source)
    mapping_rules = load_mapping_config(mapping)
    config_data: dict[str, Any] = json.loads(Path(mapping).read_text(encoding="utf-8"))
    configured_required_fields = config_data.get("required_target_fields", [])
    mapped_fields = {item.target_field for item in mapping_rules}
    unmapped_required = sorted(set(configured_required_fields) - mapped_fields)
    if unmapped_required:
        fields = ", ".join(unmapped_required)
        raise ValueError(f"Mapping configuration is missing required target fields: {fields}")

    target, transform_issues, change_counts = transform_dataframe(frame, mapping_rules)
    cleaned, cleaning_changes = clean_dataframe(target)
    for name, count in cleaning_changes.items():
        if count:
            change_counts[f"trim.{name}"] = count

    rules = [
        RuleConfig(name=f"required_{mapping.target_field}", field=mapping.target_field, required=True)
        for mapping in mapping_rules
        if mapping.required
    ]
    rules.extend(RuleConfig.model_validate(rule) for rule in config_data.get("rules", []))
    validation = validate_dataframe(cleaned, rules, expected_columns=[item.target_field for item in mapping_rules])

    exceptions = list(transform_issues)
    invalid_record_ids: set[str] = set()
    for issue in validation.issues:
        record_id = issue.record_id or (f"record-{issue.row_index + 1:06d}" if issue.row_index >= 0 else "dataset")
        if issue.row_index >= 0:
            invalid_record_ids.add(record_id)
        exceptions.append({
            "record_id": record_id,
            "source_row": issue.row_index + 2 if issue.row_index >= 0 else 0,
            "field": issue.field,
            "category": issue.code,
            "rule_id": issue.code,
        })
    invalid_record_ids.update(str(issue["record_id"]) for issue in transform_issues)
    accepted_mask = [
        f"record-{position + 1:06d}" not in invalid_record_ids
        for position in range(len(cleaned))
    ]
    accepted = cleaned.loc[accepted_mask].copy()

    summary = {
        "source_rows": len(frame),
        "prepared_rows": len(accepted),
        "exception_rows": len(invalid_record_ids),
        "exception_count": len(exceptions),
        "validation_passed": int(not exceptions),
    }
    outputs = write_preparation_outputs(accepted, exceptions, change_counts, summary, output_dir, overwrite=overwrite)
    print(json.dumps(summary | outputs, indent=2, default=str))
    return 0


def _reconcile_command(source: str, target: str, source_key: str, target_key: str) -> int:
    source_frame = read_csv_local(source)
    target_frame = read_csv_local(target)
    if source_key not in source_frame.columns or target_key not in target_frame.columns:
        raise ValueError("Source or target keys were not found in the provided files.")
    summary = reconcile_records(source_frame, target_frame, source_key, target_key, {"age": "age", "status": "status"})
    print(json.dumps(summary, indent=2, default=str))
    return 0


def _post_load_command(
    source: str,
    target: str,
    config_path: str,
    source_keys: list[str],
    target_keys: list[str],
    field_maps: list[str],
    output_dir: str,
    overwrite: bool,
) -> int:
    if len(source_keys) != len(target_keys):
        raise ValueError("The source and target key lists must have the same number of fields.")
    source_frame = read_csv_local(source)
    target_frame = read_csv_local(target)
    config_data: dict[str, Any] = json.loads(Path(config_path).read_text(encoding="utf-8"))
    configured_fields = config_data.get("required_target_fields") or [
        item.get("target_field")
        for item in config_data.get("mappings", [])
        if item.get("target_field")
    ]
    if not configured_fields:
        raise ValueError("The post-load config must define required_target_fields or target mappings.")

    rules = _load_rules(config_path)
    validation = validate_dataframe(
        target_frame,
        rules,
        expected_columns=configured_fields,
    )

    if field_maps:
        field_mapping: dict[str, str] = {}
        for field_map in field_maps:
            source_field, separator, target_field = field_map.partition("=")
            if not separator or not source_field.strip() or not target_field.strip():
                raise ValueError("Each --field-map must use source_field=target_field.")
            if source_field.strip() in field_mapping:
                raise ValueError("Each source field can appear in --field-map only once.")
            field_mapping[source_field.strip()] = target_field.strip()
    else:
        excluded = set(source_keys) | set(target_keys)
        field_mapping = {
            field_name: field_name
            for field_name in configured_fields
            if field_name not in excluded
            and field_name in source_frame.columns
            and field_name in target_frame.columns
        }

    reconciliation = reconcile_loaded_data(
        source_frame,
        target_frame,
        source_keys,
        target_keys,
        field_mapping,
    )
    report = write_post_load_reports(
        target_frame,
        validation,
        reconciliation,
        output_dir,
        overwrite=overwrite,
        config_version=str(config_data.get("schema_version", "unspecified")),
    )
    print(json.dumps({
        "run_id": report["run_id"],
        "status": report["summary"]["status"],
        "source_count": reconciliation["source_count"],
        "target_count": reconciliation["target_count"],
        "matched_key_count": reconciliation["matched_key_count"],
        "missing_target_key_count": reconciliation["missing_target_key_count"],
        "extra_target_key_count": reconciliation["extra_target_key_count"],
        "field_mismatch_count": reconciliation["field_mismatch_count"],
        "target_validation_issue_count": len(validation.issues),
        "exception_count": report["exception_count"],
        "report_files": report["report_files"],
    }, indent=2))
    return 0 if report["summary"]["status"] == "passed" else 1


def _run_demo_command(output_dir: str) -> int:
    import pandas as pd

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    source = pd.DataFrame(
        {
            "customer_id": ["C001", "C002", "C003"],
            "first_name": ["Alice", "Bob", "Charlie"],
            "age": ["30", "40", "25"],
            "status": ["active", "inactive", "active"],
        }
    )
    target = pd.DataFrame(
        {
            "customer_key": ["C001", "C003"],
            "age": [30, 25],
            "status": ["active", "active"],
        }
    )
    source.to_csv(output_path / "source_demo.csv", index=False)
    target.to_csv(output_path / "target_demo.csv", index=False)
    print(json.dumps({"source": str(output_path / "source_demo.csv"), "target": str(output_path / "target_demo.csv")}, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "profile":
        return _profile_command(args.source, args.key)
    if args.command == "validate":
        return _validate_command(args.source, args.config)
    if args.command == "prepare":
        return _prepare_command(args.source, args.mapping, args.output_dir, args.overwrite)
    if args.command == "reconcile":
        return _reconcile_command(args.source, args.target, args.source_key, args.target_key)
    if args.command == "post-load":
        return _post_load_command(
            args.source,
            args.target,
            args.config,
            args.source_key,
            args.target_key,
            args.field_map,
            args.output_dir,
            args.overwrite,
        )
    if args.command == "run-demo":
        return _run_demo_command(args.output_dir)
    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
