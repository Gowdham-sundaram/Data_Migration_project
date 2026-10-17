from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd


NULL_TOKENS = {"NA": pd.NA, "N/A": pd.NA, "null": pd.NA, "NULL": pd.NA}


def _validate_csv_structure(path: str | Path, encoding: str) -> bool:
    try:
        with Path(path).open("r", encoding=encoding, newline="") as source_file:
            reader = csv.reader(source_file, strict=True)
            header = next(reader, None)
            if header is None:
                return True
            if len(header) != len(set(header)):
                raise ValueError("CSV contains duplicate column names.")
            expected_fields = len(header)
            for row in reader:
                if row and len(row) != expected_fields:
                    raise ValueError("CSV parsing failed; check delimiter consistency and malformed rows.")
            return False
    except csv.Error as error:
        raise ValueError("CSV parsing failed; check delimiter consistency and malformed rows.") from error


def read_csv_local(path: str | Path, encoding: str | None = None) -> pd.DataFrame:
    """Read a CSV locally without emitting parser context that may contain row values."""
    encodings = [encoding] if encoding else ["utf-8-sig", "cp1252"]
    last_encoding_error: UnicodeDecodeError | None = None
    for candidate_encoding in encodings:
        try:
            if _validate_csv_structure(path, candidate_encoding):
                return pd.DataFrame()
            frame = pd.read_csv(
                path,
                dtype=str,
                keep_default_na=False,
                encoding=candidate_encoding,
                on_bad_lines="error",
            )
            return frame.replace(NULL_TOKENS)
        except UnicodeDecodeError as error:
            last_encoding_error = error
        except pd.errors.EmptyDataError:
            return pd.DataFrame()
        except pd.errors.ParserError as error:
            raise ValueError("CSV parsing failed; check delimiter consistency and malformed rows.") from error
    if last_encoding_error is not None:
        raise ValueError("CSV encoding is unsupported; provide an explicit encoding.") from last_encoding_error
    raise ValueError("CSV could not be read.")
