from pathlib import Path
import json

import pandas as pd
import pytest

from dataguard.cli import main


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "examples" / "synthetic" / "customers_dirty.csv"
TARGET = ROOT / "examples" / "synthetic" / "customers_target.csv"
MAPPING = ROOT / "config" / "sample_mapping.json"


def test_cli_profile_command_returns_zero() -> None:
    assert main(["profile", "--source", str(SOURCE)]) == 0


def test_cli_prepare_and_reconcile_end_to_end(tmp_path) -> None:
    output_dir = tmp_path / "prepared"
    assert main(["prepare", "--source", str(SOURCE), "--mapping", str(MAPPING), "--output-dir", str(output_dir)]) == 0
    assert (output_dir / "prepared_export.csv").exists()
    prepared = pd.read_csv(output_dir / "prepared_export.csv")
    assert prepared["customer_key"].tolist() == ["C006"]

    assert main([
        "reconcile",
        "--source",
        str(SOURCE),
        "--target",
        str(TARGET),
        "--source-key",
        "customer_id",
        "--target-key",
        "customer_key",
    ]) == 0


def test_prepare_quarantines_bad_rows_and_refuses_overwrite(tmp_path) -> None:
    source = tmp_path / "input.csv"
    mapping_path = tmp_path / "mapping.json"
    output_dir = tmp_path / "out"
    pd.DataFrame(
        {
            "source_id": ["A1", "B2"],
            "amount": ["25", "not-a-number"],
            "state": ["A", "secret-invalid-value"],
        }
    ).to_csv(source, index=False)
    mapping_path.write_text(
        json.dumps(
            {
                "mappings": [
                    {"source_field": "source_id", "target_field": "id", "required": True},
                    {"source_field": "amount", "target_field": "amount", "type_cast": "int"},
                    {
                        "source_field": "state",
                        "target_field": "state",
                        "value_mapping": {"A": "active"},
                    },
                ],
                "rules": [
                    {"name": "id_required", "field": "id", "required": True},
                    {"name": "amount_required", "field": "amount", "required": True, "data_type": "integer"},
                ],
            }
        ),
        encoding="utf-8",
    )

    assert main(
        [
            "prepare",
            "--source",
            str(source),
            "--mapping",
            str(mapping_path),
            "--output-dir",
            str(output_dir),
        ]
    ) == 0

    prepared = pd.read_csv(output_dir / "prepared_export.csv")
    exceptions = pd.read_csv(output_dir / "exceptions.csv")
    assert len(prepared) == 1
    assert prepared.loc[0, "id"] == "A1"
    assert {"record_id", "source_row", "field", "category", "rule_id"} == set(exceptions.columns)
    assert "secret-invalid-value" not in (output_dir / "exceptions.csv").read_text(encoding="utf-8")
    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        main(
            [
                "prepare",
                "--source",
                str(source),
                "--mapping",
                str(mapping_path),
                "--output-dir",
                str(output_dir),
            ]
        )
    assert main(
        [
            "prepare",
            "--source",
            str(source),
            "--mapping",
            str(mapping_path),
            "--output-dir",
            str(output_dir),
            "--overwrite",
        ]
    ) == 0


def test_post_load_command_writes_safe_reports_for_target_issues(tmp_path) -> None:
    source_path = tmp_path / "approved_export.csv"
    target_path = tmp_path / "target_export.csv"
    config_path = tmp_path / "post_load_config.json"
    report_dir = tmp_path / "post_load_reports"
    pd.DataFrame(
        {
            "account_key": ["A1", "A2"],
            "balance": ["100.00", "200.00"],
            "state": ["active", "inactive"],
        }
    ).to_csv(source_path, index=False)
    pd.DataFrame(
        {
            "account_key": ["A1", "A3"],
            "balance": ["100.00", "999999.00"],
            "state": ["active", "unknown-sensitive"],
        }
    ).to_csv(target_path, index=False)
    config_path.write_text(
        json.dumps(
            {
                "required_target_fields": ["account_key", "balance", "state"],
                "rules": [
                    {"name": "account_key_unique", "field": "account_key", "required": True, "unique": True},
                    {"name": "balance_range", "field": "balance", "required": True, "data_type": "number", "min_value": 0, "max_value": 10000},
                    {"name": "state_values", "field": "state", "allowed_values": ["active", "inactive"]},
                ],
            }
        ),
        encoding="utf-8",
    )

    result = main(
        [
            "post-load",
            "--source",
            str(source_path),
            "--target",
            str(target_path),
            "--config",
            str(config_path),
            "--source-key",
            "account_key",
            "--target-key",
            "account_key",
            "--output-dir",
            str(report_dir),
        ]
    )

    assert result == 1
    expected_files = {
        "post_load_summary.csv",
        "target_profile.csv",
        "post_load_exceptions.csv",
        "post_load_exception_counts.csv",
        "post_load_field_mismatches.csv",
    }
    assert {path.name for path in report_dir.iterdir()} == expected_files
    summary = pd.read_csv(report_dir / "post_load_summary.csv").iloc[0]
    assert summary["source_count"] == 2
    assert summary["target_count"] == 2
    assert summary["matched_key_count"] == 1
    assert summary["missing_target_key_count"] == 1
    assert summary["extra_target_key_count"] == 1
    assert summary["status"] == "issues_found"
    exception_text = (report_dir / "post_load_exceptions.csv").read_text(encoding="utf-8")
    assert "unknown-sensitive" not in exception_text
    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        main(
            [
                "post-load",
                "--source",
                str(source_path),
                "--target",
                str(target_path),
                "--config",
                str(config_path),
                "--source-key",
                "account_key",
                "--target-key",
                "account_key",
                "--output-dir",
                str(report_dir),
            ]
        )


def test_post_load_command_passes_when_target_matches_configured_source(tmp_path) -> None:
    source_path = tmp_path / "approved.csv"
    target_path = tmp_path / "target.csv"
    config_path = tmp_path / "rules.json"
    report_dir = tmp_path / "reports"
    matching_data = pd.DataFrame(
        {
            "key": ["X1", "X2"],
            "amount": ["3.50", "7.25"],
            "state": ["active", "inactive"],
        }
    )
    matching_data.to_csv(source_path, index=False)
    matching_data.to_csv(target_path, index=False)
    config_path.write_text(
        json.dumps(
            {
                "schema_version": "test-1",
                "required_target_fields": ["key", "amount", "state"],
                "rules": [
                    {"name": "key_unique", "field": "key", "required": True, "unique": True},
                    {"name": "amount_valid", "field": "amount", "data_type": "number", "min_value": 0},
                    {"name": "state_valid", "field": "state", "allowed_values": ["active", "inactive"]},
                ],
            }
        ),
        encoding="utf-8",
    )

    result = main(
        [
            "post-load",
            "--source",
            str(source_path),
            "--target",
            str(target_path),
            "--config",
            str(config_path),
            "--source-key",
            "key",
            "--target-key",
            "key",
            "--output-dir",
            str(report_dir),
        ]
    )

    assert result == 0
    summary = pd.read_csv(report_dir / "post_load_summary.csv").iloc[0]
    assert summary["status"] == "passed"
    assert summary["matched_key_count"] == 2
    assert summary["exact_match_count"] == 2
    assert summary["normalized_match_count"] == 0
    assert summary["config_version"] == "test-1"
    assert pd.read_csv(report_dir / "post_load_exceptions.csv").empty
