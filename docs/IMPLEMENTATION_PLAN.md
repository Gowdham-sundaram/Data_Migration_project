# Data Migration Helper implementation plan

## Checklist
- [x] Workspace inspected and confirmed empty
- [x] Project skeleton and configuration created
- [x] Synthetic fixtures and profiling logic implemented
- [x] Mapping, cleaning, transformation, and validation modules implemented
- [x] Export preparation, reconciliation, and reporting implemented
- [x] CLI and demo workflow implemented
- [x] Automated tests added and passes
- [x] README, privacy/security docs, and CI configuration finalized

## Phase overview
1. Foundation: create package layout, config models, security redaction utilities, and initial documentation.
2. Profiling: implement source discovery, schema inference, anomaly detection, and duplicate checks with unit tests.
3. Mapping and cleaning: declarative config, transformation rules, and pre-migration validation.
4. Export/reconciliation: clean output generation, target validation, and source-target comparison.
5. Reporting/CLI/demo: aggregate dataset outputs, CLI entry points, and synthetic demo assets.
6. Final validation: run pytest, demo commands, and fix findings before summarizing.

## Decisions
- The framework works entirely locally using synthetic files.
- No external AI or proprietary tool integrations are included.
- Data exports are intentionally safe, aggregate-only where practical, and never include raw sensitive records.
- Config is declarative and schema-validated through Pydantic models.

## Strengthening work completed
- Profiling is field-agnostic and reports separate null/blank counts, inferred type, distinct values, duplicate-value rows, candidate-key duplicate counts, numeric ranges, potential IQR outliers, date-format anomalies, and safe CSV parse failures.
- Validation rules now come from the supplied JSON config rather than customer-specific CLI defaults.
- Transformations are explicit and deterministic. Failed type casts and unknown code mappings retain no silently corrected value and are routed to safe, generated-record-ID exceptions.
- Preparation quarantines any row with a transformation or validation exception, writes only accepted rows to the prepared export, and records exception/change/run aggregates in separate files.
- Generated outputs refuse replacement by default. `--overwrite` is the explicit opt-in.
- Latest local verification: `py -m pytest -q` passed 12 tests; CLI profile, prepare, and config-driven validate smoke commands passed on synthetic input.
- Added a standalone customer-facing browser UI prototype at `examples/ui/data-migration-helper.html`. It supports local delimited-file selection, rule configuration, good/review previews, and an explicit in-session approval gate before the ready CSV download.
- Added a customer quick-start and a plain-language description of profiling usefulness and limitations to the README and the UI's expandable help panel.
- Added a `post-load` CLI stage that validates a target export against configured target rules and reconciles it with the approved export using configurable keys and field pairs. It reports missing/extra records, null/duplicate keys, exact/normalized matches, and field mismatches in privacy-safe, overwrite-protected local reports.
- Latest verification after post-load work: `py -m pytest -q` passed 18 tests; a synthetic prepare-to-post-load CLI run produced the expected issue-found status and all five post-load report files. Pylance diagnostics are clear for the post-load module and CLI.
- Expanded the browser UI's mapping stage with editable target names and explicit trim/case, date/number/currency formatting, exact-delimiter split, and two-field combine operations. Profiling and user-selected checks now run on transformed target fields; conversion failures and invalid mappings block approval or route affected rows to review. The review export contains source and proposed target values for local remediation.
- Renamed the user-facing project and browser UI file to Data Migration Helper. Added a confirmation-gated **Clear loaded data** action and confirmation before replacing in-memory data with another upload or the synthetic sample.

## Remaining limitations
- Data Migration Helper does not infer business meaning or invent correction rules; schema/mapping rules still require a reviewed specification.
- The HTML UI is a separate demo prototype, not a production service and not wired to the Python pipeline; its approval is not persisted.
- The browser mapping and transformation settings are not generated from customer requirements. A data owner must supply/approve the target schema, formats, and validation rules; conversions deliberately do not guess.
- Post-load checks inspect a user-supplied target export only. They do not connect to a live target system, trigger data repair/rollback, or integrate with any migration product.
- Exception records deliberately contain identifiers and rule categories only, not source values. Review the corresponding source row locally to remediate an exception.
- CSV dialect support is conservative and comma-delimited; malformed field counts fail the read instead of being silently repaired.
- Output file sets are staged before publication, but a filesystem failure during multi-file publication may require checking the output folder before rerunning.
