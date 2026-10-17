from __future__ import annotations

import os
from pathlib import Path
import tempfile
from typing import Any

import pandas as pd


def prepare_export(
    frame: pd.DataFrame,
    output_dir: str | Path,
    basename: str = "prepared_export.csv",
    overwrite: bool = False,
) -> dict[str, str]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    final_path = output_path / basename
    if final_path.exists() and not overwrite:
        raise FileExistsError(f"Output path already exists: {final_path}")

    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="", suffix=".csv", dir=output_path, delete=False) as temp_file:
        temporary_path = Path(temp_file.name)
    reserved = False
    published = False
    try:
        frame.to_csv(temporary_path, index=False)
        if not overwrite:
            with final_path.open("xb"):
                pass
            reserved = True
        os.replace(temporary_path, final_path)
        published = True
    finally:
        temporary_path.unlink(missing_ok=True)
        if reserved and not published:
            final_path.unlink()
    return {"prepared_path": str(final_path)}


def write_exceptions(
    issues: list[dict[str, object]],
    output_dir: str | Path,
    basename: str = "exceptions.csv",
    overwrite: bool = False,
) -> dict[str, str]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    final_path = output_path / basename
    if final_path.exists() and not overwrite:
        raise FileExistsError(f"Output path already exists: {final_path}")
    return prepare_export(pd.DataFrame(issues), output_path, basename, overwrite)


def write_preparation_outputs(
    prepared: pd.DataFrame,
    exceptions: list[dict[str, Any]],
    change_counts: dict[str, int],
    summary: dict[str, int | str],
    output_dir: str | Path,
    overwrite: bool = False,
) -> dict[str, str]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    named_outputs = {
        "prepared_path": output_path / "prepared_export.csv",
        "exceptions_path": output_path / "exceptions.csv",
        "changes_path": output_path / "changes_summary.csv",
        "summary_path": output_path / "run_summary.csv",
    }
    existing = [str(path) for path in named_outputs.values() if path.exists()]
    if existing and not overwrite:
        raise FileExistsError(f"Refusing to overwrite existing output: {existing[0]}")

    changes_frame = pd.DataFrame(
        [{"change": name, "count": count} for name, count in sorted(change_counts.items())],
        columns=["change", "count"],
    )
    summary_frame = pd.DataFrame([summary])
    staged: dict[str, Path] = {}
    reserved_paths: set[Path] = set()
    published_paths: set[Path] = set()
    try:
        for name, frame in (
            ("prepared_path", prepared),
            ("exceptions_path", pd.DataFrame(exceptions, columns=["record_id", "source_row", "field", "category", "rule_id"])),
            ("changes_path", changes_frame),
            ("summary_path", summary_frame),
        ):
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="", suffix=".csv", dir=output_path, delete=False) as temp_file:
                staged[name] = Path(temp_file.name)
            frame.to_csv(staged[name], index=False)
        if not overwrite:
                for final_path in named_outputs.values():
                    with final_path.open("xb"):
                        pass
                    reserved_paths.add(final_path)
        for name, final_path in named_outputs.items():
                os.replace(staged[name], final_path)
                published_paths.add(final_path)
    finally:
        for temporary_path in staged.values():
                temporary_path.unlink(missing_ok=True)
        for final_path in reserved_paths - published_paths:
                final_path.unlink(missing_ok=True)
    return {name: str(path) for name, path in named_outputs.items()}
