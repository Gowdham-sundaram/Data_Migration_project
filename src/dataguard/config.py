from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, ConfigDict


class RuleConfig(BaseModel):
    """Declarative, data-independent validation rule."""

    model_config = ConfigDict(extra="forbid")

    name: str
    field: str
    enabled: bool = True
    required: bool = False
    data_type: str | None = None
    min_value: float | None = None
    max_value: float | None = None
    allowed_values: list[str] | None = None
    regex: str | None = None
    date_format: str | None = None
    unique: bool = False
    equals_field: str | None = None


class MappingConfig(BaseModel):
    """Source-to-target field mapping configuration."""

    model_config = ConfigDict(extra="forbid")

    source_field: str
    target_field: str
    required: bool = False
    default_value: Any | None = None
    transform: str | None = None
    type_cast: str | None = None
    value_mapping: dict[str, str] = Field(default_factory=dict)
    allowed_values: list[str] | None = None


class DataMigrationHelperConfig(BaseModel):
    """Top-level project configuration."""

    model_config = ConfigDict(extra="forbid")

    project_name: str = "Data Migration Helper"
    source_path: str
    target_path: str | None = None
    output_dir: str = "output"
    schema_version: str = "1.0"
    business_key: list[str] = Field(default_factory=list)
    required_target_fields: list[str] = Field(default_factory=list)
    mappings: list[MappingConfig] = Field(default_factory=list)
    rules: list[RuleConfig] = Field(default_factory=list)


DataGuardConfig = DataMigrationHelperConfig
