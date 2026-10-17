import pandas as pd

from dataguard.post_load import reconcile_loaded_data
from dataguard.validation import validate_dataframe


def test_post_load_reconciliation_reports_gaps_duplicates_nulls_and_field_mismatches() -> None:
    source = pd.DataFrame(
        {
            "source_id": ["A", "B", "C", ""],
            "name": ["Maya", "Jon", "Casey", "No key"],
            "amount": ["10", "20", "30", "40"],
        }
    )
    target = pd.DataFrame(
        {
            "target_id": ["A", "B", "D", "A", ""],
            "name": [" Maya ", "Jonathan", "Extra", "Maya", "No key"],
            "amount": ["10", "21", "50", "10", "40"],
        }
    )

    result = reconcile_loaded_data(
        source,
        target,
        ["source_id"],
        ["target_id"],
        {"name": "name", "amount": "amount"},
    )

    assert result["source_count"] == 4
    assert result["target_count"] == 5
    assert result["matched_key_count"] == 2
    assert result["missing_target_key_count"] == 1
    assert result["extra_target_key_count"] == 1
    assert result["source_null_key_rows"] == 1
    assert result["target_null_key_rows"] == 1
    assert result["target_duplicate_key_count"] == 1
    assert result["target_duplicate_key_rows"] == 2
    assert result["exact_match_count"] == 0
    assert result["normalized_match_count"] == 1
    assert result["field_mismatch_count"] == 2
    assert result["field_mismatch_counts"] == {"name->name": 1, "amount->amount": 1}
    assert result["status"] == "issues_found"
    assert "Maya" not in str(result)
    assert "Jonathan" not in str(result)


def test_post_load_validation_is_target_schema_configurable() -> None:
    target = pd.DataFrame(
        {
            "policy_id": ["P1", "P2"],
            "premium": ["250.00", "invalid-premium"],
            "state": ["active", "unknown"],
        }
    )
    validation = validate_dataframe(
        target,
        [
            {"field": "policy_id", "required": True, "unique": True},
            {"field": "premium", "required": True, "data_type": "number", "min_value": 0},
            {"field": "state", "allowed_values": ["active", "inactive"]},
        ],
        expected_columns=["policy_id", "premium", "state"],
    )
    assert validation.valid is False
    assert {issue.code for issue in validation.issues} == {"invalid_type", "not_allowed"}


def test_missing_target_key_field_is_reportable_not_a_silent_reconciliation() -> None:
    source = pd.DataFrame({"business_id": ["A1"], "amount": ["4"]})
    target = pd.DataFrame({"amount": ["4"]})

    result = reconcile_loaded_data(
        source,
        target,
        ["business_id"],
        ["target_id"],
        {"amount": "amount"},
    )

    assert result["status"] == "issues_found"
    assert result["missing_target_key_count"] is None
    assert result["missing_target_key_fields_count"] == 1
    assert result["exceptions"] == [
        {
            "stage": "reconciliation",
            "record_id": "target-dataset",
            "field": "target_id",
            "category": "missing_target_key_field",
            "rule_id": "reconciliation.target_key_schema",
        }
    ]


def test_post_load_supports_composite_keys_and_differently_named_fields() -> None:
    source = pd.DataFrame({"tenant": ["T1", "T1"], "account": ["A1", "A2"], "label": ["North", "South"]})
    target = pd.DataFrame({"org": ["T1", "T1"], "account_ref": ["A1", "A2"], "display_name": ["north", "South"]})

    result = reconcile_loaded_data(
        source,
        target,
        ["tenant", "account"],
        ["org", "account_ref"],
        {"label": "display_name"},
    )

    assert result["matched_key_count"] == 2
    assert result["normalized_match_count"] == 1
    assert result["exact_match_count"] == 1
    assert result["field_mismatch_count"] == 0
