from pathlib import Path

from dataguard.profiler import profile_csv, profile_dataframe


FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "customers_profile.csv"


def test_profile_csv_detects_duplicates_and_missing_values() -> None:
    result = profile_csv(FIXTURE_PATH, candidate_keys=[["customer_id"]])

    assert result["row_count"] == 6
    assert result["column_count"] == 6
    assert result["duplicate_candidate_key_rows"]["customer_id"] == 2
    assert result["column_metrics"]["last_name"]["blank_count"] == 1
    assert result["column_metrics"]["status"]["blank_count"] == 1


def test_profile_dataframe_flags_invalid_dates_and_numeric_values() -> None:
    result = profile_csv(FIXTURE_PATH)
    assert "contains_invalid_date_values" in result["column_metrics"]["signup_date"]["format_issues"]
    assert "contains_non_numeric_values" in result["column_metrics"]["age"]["format_issues"]
    assert result["column_metrics"]["age"]["inferred_type"] == "mixed"


def test_profile_reports_nulls_blanks_ranges_and_explicit_candidate_keys() -> None:
    import pandas as pd

    result = profile_dataframe(
        pd.DataFrame(
            {
                "code": ["A", "A", None, "B"],
                "amount": ["1", "2", "3", "100"],
                "note": ["x", " ", "", "y"],
            }
        ),
        candidate_keys=[["code"], ["code", "amount"]],
    )

    assert result["column_metrics"]["code"]["null_count"] == 1
    assert result["column_metrics"]["note"]["blank_count"] == 2
    assert result["column_metrics"]["amount"]["numeric_range"] == {"min": 1.0, "max": 100.0}
    assert result["column_metrics"]["amount"]["potential_numeric_outlier_count"] > 0
    assert result["column_metrics"]["code"]["inferred_type"] == "string"
    assert result["duplicate_candidate_key_rows"] == {"code": 2, "code+amount": 0}


def test_profile_handles_empty_and_malformed_csv_without_echoing_row_values(tmp_path) -> None:
    empty_path = tmp_path / "empty.csv"
    empty_path.write_text("", encoding="utf-8")
    empty_result = profile_csv(empty_path)
    assert empty_result["row_count"] == 0
    assert empty_result["parse_warnings"] == ["empty_file"]

    malformed_path = tmp_path / "malformed.csv"
    malformed_path.write_text("id,value\n1,secret-row-value,unexpected\n", encoding="utf-8")
    try:
        profile_csv(malformed_path)
    except ValueError as error:
        assert "secret-row-value" not in str(error)
        assert "CSV parsing failed" in str(error)
    else:
        raise AssertionError("Malformed CSV should be rejected.")
