from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


def build_aggregate_report(rows: list[dict[str, Any]], output_dir: str | Path, filename: str = "aggregate_metrics.csv") -> dict[str, str]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    final_path = output_path / filename

    frame = pd.DataFrame(rows)
    frame.to_csv(final_path, index=False)
    return {"aggregate_report_path": str(final_path)}
