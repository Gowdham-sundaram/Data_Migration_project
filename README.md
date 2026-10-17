# Data Migration Helper

Data Migration Helper is a locally runnable Python framework for data migration preparation, validation, and reconciliation using synthetic CSV datasets. The goal is to help a team profile a source dataset, map it to target fields, clean and validate values, prepare a migration export, and reconcile source versus target results without relying on proprietary migration tooling or cloud services.

## Scope
- Source discovery and profiling for CSV inputs
- Declarative mapping configuration
- Cleaning and normalization rules
- Validation of required fields, ranges, and allowed values
- Export preparation and exception tracking
- Source-target reconciliation and mismatch reporting
- Aggregate CSV reporting for Power BI-style review
- Local-only processing with privacy-safe logging conventions

## Local setup

1. Open a terminal in the project root.
2. Create and activate a virtual environment:
   - Windows PowerShell: `py -m venv .venv` and `./.venv/Scripts/Activate.ps1`
3. Install dependencies:
   - `py -m pip install -e .`
4. Run tests:
   - `py -m pytest -q`

## CLI usage

After installation, the project exposes the `data-migration-helper` command.

- `data-migration-helper profile --source examples/synthetic/customers_dirty.csv --key customer_id`
- `data-migration-helper validate --source output/prepared_export.csv --config config/sample_mapping.json`
- `data-migration-helper prepare --source examples/synthetic/customers_dirty.csv --mapping config/sample_mapping.json --output-dir output`
- `data-migration-helper reconcile --source examples/synthetic/customers_dirty.csv --target examples/synthetic/customers_target.csv --source-key customer_id --target-key customer_key`
- `data-migration-helper post-load --source output/prepared_export.csv --target target_export.csv --config config/sample_mapping.json --source-key customer_key --target-key customer_key --output-dir reports/post_load`
- `data-migration-helper run-demo --output-dir reports/demo_aggregate`



## Profiling, rules, and preparation behavior

Profiling is data-driven: it reports per-column inferred type, nulls, blanks, distinct and duplicate-value rows, numeric ranges and potential IQR outliers. Candidate keys are explicitly chosen with `--key`; repeat the option for additional candidates, and use comma-separated field names for a composite key. Outliers and format flags are indicators for review, not automatic errors.

The JSON mapping file can contain:
- `mappings`: source-to-target fields, explicit defaults, approved transforms (`trim`, `lower`, `upper`), casts (`str`, `int`, `float`, `date`), code mappings, and allowed values
- `required_target_fields`: target columns that must be mapped
- `rules`: field rules for required values, types, ranges, allowed values, regex/date formats, uniqueness, and cross-field equality

`prepare` only applies configured conversions plus safe whitespace trimming. Failed casts, unmapped codes, missing required values, and validation failures are quarantined by generated record ID and source row number. The exception file intentionally contains rule/category metadata, not raw values; consult the original local source using those references to resolve exceptions. Rows with any exception are excluded from `prepared_export.csv`, but are counted and listed in `exceptions.csv`; no row is silently dropped.

Preparation creates `prepared_export.csv`, `exceptions.csv`, `changes_summary.csv`, and `run_summary.csv`. It refuses to replace any of those outputs by default. To explicitly replace existing outputs, pass `--overwrite`. Validate and profile commands do not mutate source files.

## Post-load validation and reconciliation

After the separate migration process produces a target export, run `post-load` with the approved prepared export as `--source` and the target export as `--target`. The command validates the target against the configured target fields and rules, then reconciles configured business keys and comparable fields. Specify `--source-key` and `--target-key` once per key field in the same order for composite keys. If compared columns have different names, use repeatable `--field-map source_field=target_field` arguments. Otherwise, configured fields with the same name are compared automatically.

The command writes `post_load_summary.csv`, `target_profile.csv`, `post_load_exceptions.csv`, `post_load_exception_counts.csv`, and `post_load_field_mismatches.csv` into the selected local output folder. Reports contain counts, field/rule identifiers, and generated row IDs; they do not contain business-key or field values. Exit code `0` means configured checks and reconciliation found no issues; exit code `1` means review is required. Existing reports are not overwritten unless `--overwrite` is supplied.

This automation validates only the target export/sample results provided by the user. It does not inspect a live destination, trigger rollback or repair, or integrate with a proprietary migration tool. Resolve reported issues through the responsible migration/data owner and rerun against a fresh target export.

## Demo assets

The repository includes synthetic examples in `examples/synthetic/` and a sample mapping file in `config/sample_mapping.json`.

## Customer-friendly UI prototype

Open `examples/ui/data-migration-helper.html` in a modern browser to try the standalone review interface. It accepts comma-, tab-, semicolon-, and pipe-delimited text files up to 20 MB and processes them in the browser.

For a visual end-to-end diagram and a plain-language explanation of each stage, see [the customer workflow guide](docs/customer_workflow.md).

### Customer quick-start

#### Start the HTML page on Windows

1. Open **File Explorer** and go to your project folder.
2. Open `examples`, then `ui`.
3. Right-click `data-migration-helper.html`, choose **Open with**, and select **Microsoft Edge** or **Google Chrome**. (If you are already in VS Code, right-click the file and choose **Reveal in File Explorer** first.)
4. The page opens directly in your browser; you do not need to run Python, install anything, or start a web server. It should show **Data Migration Helper** and the **Load synthetic sample** button.

#### Try the included sample data

1. On the page, click **Load synthetic sample**. This built-in fictional sample has checks already selected, so you can immediately see the profile and **Ready / Needs review** results.
2. To try a sample file instead, click **Clear loaded data** if a file is already loaded, confirm, then click **Choose a file**.
3. In the file picker, browse to `examples\synthetic` and select `customers_dirty.csv`. This sample includes a repeated customer ID, missing names/values, an invalid date, and a non-numeric age. Select appropriate required/type/unique checks in **Profile & define checks** to see which rows need review.
4. Optionally load `customers_target.csv` the same way. It is a cleaner target-style sample, not the dirty source sample. The UI treats it as an ordinary input file.

#### Use your own delimited file

1. Click **Choose a file** or drop a file onto the upload area. The first row must contain unique column names. Supported files are CSV/TSV and other comma-, tab-, semicolon-, or pipe-delimited text up to 20 MB; Excel workbooks are not supported.
2. Read the profile summary. It shows row/column counts, blank cells, repeated field values, detected types, distinct values, and numeric ranges when the whole column looks numeric.
3. In **Map & transform**, target names start as the source names. You may rename them and explicitly choose keep, trim, upper/lowercase, date formatting (`YYYY`, `MM`, `DD` tokens), numeric/currency formatting, or splitting a field at an exact delimiter. The combine controls create an additional target field from two chosen source fields with a chosen separator. Failed conversions and split attempts that cannot find the delimiter go to review; they are not silently repaired.
4. In **Profile & define checks**, confirm each detected target-field type and select only requirements agreed with the data owner. You can mark fields required, select an expected type, list allowed values separated with `|`, and require uniqueness. A meaningful check must be configured before approval is enabled.
5. Inspect both the **Ready** and **Needs review** previews. The preview shows a limited number of rows; use the downloads to inspect the full output. The approved file uses transformed target fields, while the review file includes source and proposed target values plus generated issue categories for remediation.
6. Resolve rejected rows using **Download review file** and the original source data. Do not assume duplicate-looking values are errors, and do not change data without an approved rule.
7. Review the Ready rows. Check the confirmation box and choose **Approve ready data**. Approval is only for this browser session and current mapping/checks. Any mapping, transformation, or rule change clears the approval.
8. After approval, choose **Download approved CSV**. Only this approved ready file is intended to continue to a separate transformation tool. Data Migration Helper does not send it to one.
9. To remove the uploaded data and review state from the browser tab, choose **Clear loaded data** and confirm. This does not delete the original file or downloads. Choosing another file or loading the sample also asks before replacing the current in-memory data.

Transformations are explicit formatting operations, not inferred business mappings. Date formats must specify all three tokens (`YYYY`, `MM`, `DD`); numeric/currency inputs need the correct decimal and grouping separators. Splitting trims outer whitespace and uses the first exact delimiter occurrence, trimming each resulting part. Combining trims the chosen values, omits blanks, and joins the remainder. Verify the output against a data-owner-approved target specification before using it downstream.

### How useful is this profiling?

This interface is useful for **quick, visual first-pass triage and guided review**, especially to identify blanks, repeated values, obvious mixed types, numeric ranges, and records that violate simple checks explicitly selected by the reviewer. It can help a user separate rows that pass those selected checks from rows needing attention.

It is **not a comprehensive data-quality assessment or proof that records are correct**. It cannot infer required fields or business meaning, reliably identify near-duplicates, analyze relationships between multiple fields, determine valid ranges unless users configure checks, or replace a schema-aware production profiling process. A repeated value in an individual column is only a signal: it does not mean the whole record is duplicated. The UI is a small-file delimited-text prototype and performs a limited set of browser-side checks; use the Python framework and reviewed configuration for more complete configured validation.

This is a browser-only prototype, not a production upload portal or connection to the Python CLI or any migration tool. It does not persist approval, validate uploaded content against a server-side schema, or support Excel workbooks. The review download includes original field values so users can investigate flagged rows; it is local, row-level data and must be handled as sensitive. Use synthetic data for demonstrations.

## Privacy and security constraints

The application code processes data locally and contains no cloud API, telemetry, or external AI calls. This is not a guarantee about the computer, browser, editor, or storage provider: the current project folder is under OneDrive and may be synchronized by OneDrive according to its settings. Browser downloads go to the browser's configured download location. Do not use confidential or regulated data unless the device, browser, storage location, and organizational policies are approved for it. For stronger isolation, use synthetic data or a managed, non-synced local environment with networking disabled. See `docs/privacy_security.md` for the full guidance and limitations.

## Power BI ready reporting

The aggregate reporting output is generated as CSV files in a sanitized, aggregate-only format suitable for import into Power BI Desktop; the data remains local to the user environment. Power BI licensing and availability are outside the scope of this project. See `docs/dashboard_guide.md` for the internal and customer-facing aggregate dashboard design guidance.

## Current status

This remains a proof-of-concept local framework. Profiling, rule validation, deterministic transformations, row-level exception references, and guarded preparation are covered by unit and integration tests. It does not infer business meaning, auto-correct ambiguous values, or claim that every possible CSV dialect/schema is supported. Review and test mapping and validation rules against the actual target specification before using any export.
