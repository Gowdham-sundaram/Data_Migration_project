# Privacy and security limits

## Local-only processing
The application code processes files locally. The browser UI uses no remote scripts, stylesheets, fonts, images, frames, or network APIs; the Python runtime source contains no network client integrations, cloud APIs, or telemetry. This describes this project's code paths, not the entire device or execution environment.

**This does not guarantee that data cannot be synchronized or transmitted by other software.** This workspace is located under a OneDrive directory; if OneDrive sync is enabled, files saved there may be uploaded by OneDrive. Browser downloads use the browser's configured destination, which may also be synced. The browser, operating system, editor, endpoint-protection tools, backup software, or a future code change may have separate network behavior outside this project's control. Do not load confidential or regulated data unless the device, storage destination, browser, and organizational policies are approved. For stronger isolation, use synthetic data or a managed, non-synced local environment with networking disabled.

## Synthetic data only
This project uses fictional customer names and identifiers only. No real customer, medical, or confidential records should be loaded into the workflow.

## Deterministic logic only
The project does not use external AI or LLM-based processing in the runtime pipeline. Profiling, validation, transformation, and reconciliation are all implemented using local deterministic code.

## Redaction and safe logging
The framework avoids logging raw row contents. Logged values should be sanitized through the redaction utilities in `src/dataguard/security.py` using record IDs, rule IDs, safe categories, and aggregate counts instead of sensitive field values.

## Data handling guardrails
- No raw sensitive values in logs or console output
- No silent data deletion or overwrites without explicit configuration
- No automatic deduplication without conscious, documented rules
- Ambiguous cases should be routed to exception reporting for human review
- Preparation exception files contain generated row IDs, source row positions, field names, and safe rule/category codes, but never source values. Treat them as operationally sensitive because they identify affected rows; keep generated output folders local and out of source control.
- The standalone browser UI prototype reads a selected delimited-text file locally in browser memory and does not transmit it. Its optional review download includes the flagged rows' original fields and proposed transformed fields to support human review; that file is row-level sensitive data and should be stored only in an approved local location. The UI prototype is not a production security boundary.
- Browser transformations are deterministic and user-configured: target-column renaming, explicit text casing/trim, specified date and number/currency formats, exact-delimiter splitting, and combining two selected fields. They do not infer customer requirements or automatically correct ambiguous values. Failed conversions are routed to review with a category rather than the source value in the issue text.
- Aggregate reports should avoid row-level data and instead expose counts, rates, and summary metrics

## Compliance
This project does not claim HIPAA, GDPR, or other legal compliance. Formal compliance requires a separate independent assessment based on the actual deployment environment and dataset classifications.
