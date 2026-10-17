import pandas as pd
import pytest

from dataguard.cleaning import clean_dataframe
from dataguard.config import MappingConfig
from dataguard.mapping import apply_mapping, transform_dataframe
from dataguard.validation import validate_dataframe


def test_mapping_and_cleaning_produce_expected_target_shape() -> None:
    source = pd.DataFrame(
        {
            "customer_id": ["C001", " C002 "],
            "first_name": [" Alice ", "Bob"],
            "signup_date": ["2024-01-15", "2024-02-22"],
            "age": ["33", "45"],
        }
    )

    mappings = [
        MappingConfig(source_field="customer_id", target_field="customer_key", required=True),
        MappingConfig(source_field="first_name", target_field="first_name", transform="trim"),
        MappingConfig(source_field="signup_date", target_field="signup_date", type_cast="str"),
        MappingConfig(source_field="age", target_field="age", type_cast="int"),
    ]

    target = apply_mapping(source, mappings)
    cleaned, summary = clean_dataframe(target)

    assert list(target.columns) == ["customer_key", "first_name", "signup_date", "age"]
    assert cleaned.loc[0, "customer_key"] == "C001"
    assert cleaned.loc[1, "first_name"] == "Bob"
    assert cleaned.loc[0, "age"] == 33
    assert summary == {"trimmed": 1}


def test_validation_flags_missing_and_out_of_range_values() -> None:
    frame = pd.DataFrame(
        {
            "customer_key": ["C001", ""],
            "age": [18, 150],
            "status": ["active", "unknown"],
        }
    )

    rules = [
        {"field": "customer_key", "required": True},
        {"field": "age", "min_value": 18, "max_value": 120},
        {"field": "status", "allowed_values": ["active", "inactive"]},
    ]

    result = validate_dataframe(frame, rules)

    assert result.valid is False
    assert any(issue.code == "missing_required" for issue in result.issues)
    assert any(issue.code == "above_max" for issue in result.issues)
    assert any(issue.code == "not_allowed" for issue in result.issues)


def test_transform_routes_bad_casts_and_unmapped_codes_without_exposing_values() -> None:
    source = pd.DataFrame({"amount": ["12", "not-a-number"], "state": ["A", "X"]})
    mappings = [
        MappingConfig(source_field="amount", target_field="amount", type_cast="int"),
        MappingConfig(
            source_field="state",
            target_field="state",
            value_mapping={"A": "active", "I": "inactive"},
        ),
    ]

    transformed, issues, changes = transform_dataframe(source, mappings)

    assert transformed.loc[0, "amount"] == 12
    assert transformed.loc[1, "amount"] == "not-a-number"
    assert transformed.loc[0, "state"] == "active"
    assert {issue["category"] for issue in issues} == {"invalid_type_conversion", "unmapped_code"}
    assert all("not-a-number" not in str(issue) and "'X'" not in str(issue) for issue in issues)
    assert changes["amount.cast_int"] == 1
    with pytest.raises(ValueError, match="Use transform_dataframe"):
        apply_mapping(source, mappings)


def test_validation_checks_schema_type_format_uniqueness_and_cross_field_rules() -> None:
    frame = pd.DataFrame(
        {
            "key": ["K1", "K1", ""],
            "start": ["2024-01-01", "bad", "2024-01-03"],
            "end": ["2024-01-01", "2024-02-01", "2024-01-03"],
        }
    )
    result = validate_dataframe(
        frame,
        [
            {"field": "key", "required": True, "unique": True},
            {"field": "start", "data_type": "date", "date_format": "%Y-%m-%d", "equals_field": "end"},
        ],
        expected_columns=["key", "start", "end", "extra"],
    )

    codes = {issue.code for issue in result.issues}
    assert {"duplicate_key", "missing_required", "invalid_date", "invalid_type", "missing_column"} <= codes
    assert "unexpected_column" not in codes
    assert all("2024" not in issue.message and "K1" not in issue.message for issue in result.issues)


def test_validation_rejects_empty_dataset() -> None:
    result = validate_dataframe(pd.DataFrame(columns=["id"]), [{"field": "id", "required": True}])
    assert result.valid is False
    assert [issue.code for issue in result.issues] == ["empty_dataset"]
