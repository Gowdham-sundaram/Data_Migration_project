# Dashboard design guide

## Internal technical dashboard
This dashboard should focus on count-based operational metrics rather than raw customer details. Suggested tiles include:
- Source row count and processed row count
- Null and blank counts by field
- Duplicate candidate counts and unique record-key counts
- Invalid-date or invalid-number counts
- Pipeline stage status per run
- Exception categories by volume
- Reconciliation summary: matched, missing, extra, and mismatch counts

## Customer-facing aggregate dashboard
This view should use non-identifying summary metrics only:
- Total records by business domain
- Records accepted vs rejected
- Percent of rows requiring manual review
- Quality score by data domain
- Distribution of issue classes
- Run-to-run trend lines

## Reporting output pattern
All dashboards should consume sanitized aggregate CSV files from the `reports/` or `output/` directories. Raw row-level data should not be included in Power BI datasets.
