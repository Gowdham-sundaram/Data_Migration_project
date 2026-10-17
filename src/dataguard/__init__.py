"""Data Migration Helper package (legacy ``dataguard`` import namespace)."""

from .audit import build_audit_record, generate_run_id
from .cleaning import clean_dataframe, normalize_date, normalize_text
from .config import DataGuardConfig, DataMigrationHelperConfig, MappingConfig, RuleConfig
from .exporter import prepare_export, write_exceptions
from .mapping import apply_mapping, load_mapping_config
from .post_load import build_post_load_exceptions, reconcile_loaded_data, write_post_load_reports
from .profiler import profile_csv, profile_dataframe
from .reconciliation import reconcile_records
from .reporting import build_aggregate_report
from .validation import ValidationIssue, ValidationResult, validate_dataframe

__all__ = [
    "DataMigrationHelperConfig",
    "DataGuardConfig",
    "MappingConfig",
    "RuleConfig",
    "profile_csv",
    "profile_dataframe",
    "apply_mapping",
    "load_mapping_config",
    "clean_dataframe",
    "normalize_date",
    "normalize_text",
    "ValidationIssue",
    "ValidationResult",
    "validate_dataframe",
    "prepare_export",
    "write_exceptions",
    "reconcile_records",
    "reconcile_loaded_data",
    "build_post_load_exceptions",
    "write_post_load_reports",
    "build_aggregate_report",
    "generate_run_id",
    "build_audit_record",
]
