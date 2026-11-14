# Dataset preparation and source access

## Job postings

Download the CSV from the dataset owner's Kaggle page after reviewing its license and
access requirements: https://www.kaggle.com/datasets/shivamb/real-or-fake-fake-jobposting-prediction
Extract `fake_job_postings.csv` into `data/`. Do not substitute a guessed schema or row count.
The page was reachable but did not expose readable schema content during this inspection.

## Phishing reports

Read the publisher's developer guide: https://phishtank.org/developer_info.php
It documents a CSV snapshot at `https://data.phishtank.com/data/online-valid.csv`.
Download only the publisher snapshot, never any URL contained in its records. Preserve
the downloaded CSV as `data/phishing_reports.csv`; decompress it first if necessary.
The publisher requests a descriptive User-Agent and recommends an application key for
automated downloads. Keep keys private and respect rate limits; do not repeatedly retry blocks.

The documentation lists `phish_id,url,phish_detail_url,submission_time,verified,verification_time,online,target`.
These fields now match the inspected local header below. This is a snapshot of online,
verified reports, not all phishing incidents or a representative population of safe/unsafe sites.

Both snapshots are now present and readable. The user reports successful downloads;
acquisition was not independently authenticated by the inspector. If future acquisition fails, record the date, HTTP status/error and
source in a local provenance note. Use only clearly labelled synthetic development fixtures
until acquisition succeeds. The validator self-test supplies temporary synthetic rows with
reserved `.invalid` hosts; it never creates a substitute real dataset or contacts those hosts.

## Inspect and record provenance

Run `python scripts/inspect_data.py` after placing both CSVs. It inspects the actual headers,
row widths, empty cells, duplicate rows and key duplicates when candidate identifiers exist.
It records a SHA-256 checksum and row count without exposing URLs or text samples.
CSV values are strings; proposed warehouse types below are based on full-file checks.
No warehouse schema or SQL models have been created.
Structural success alone does not establish semantic correctness or source authenticity.

For each snapshot record source page, download time with timezone, original filename,
license/usage terms, checksum (from the profile), any renaming/conversion and whether it
is real or synthetic. Keep signed URLs, keys and private dataset content out of Git.
Do not build staging SQL until the real profile has been reviewed.

## Supported Airbyte file-source choices (planning only)

Official reference: https://docs.airbyte.com/integrations/sources/file

- HTTPS: a direct, approved downloadable CSV reachable from the connector worker.
  A Kaggle webpage requiring login is not a direct CSV URL.
- GCS, S3 or SFTP: supported provider options; configure private access in Phase 3.
  Creating paid storage requires approval first.
- Local filesystem: self-hosted only. The docs describe `/local/` paths and the
  `/tmp/airbyte_local` location, but visibility depends on deployment and worker mounts.
  A Windows `C:\...` path is not automatically visible inside a connector container.
  Validate mounts in the selected deployment before choosing this option. Airbyte Cloud
  cannot read laptop-local files. Do not assume legacy Compose mounts work with abctl.

The current local deployment guide uses abctl (Kubernetes via Docker):
https://docs.airbyte.com/platform/using-airbyte/getting-started/oss-quickstart
Do not install an old all-in-one Compose stack from a tutorial. Choose platform and
connector versions together in Phase 3, inspect inferred source fields, configure two
separate connections, and verify real sync job IDs and BigQuery counts. None of those
actions have been performed in Phase 1.

## Verified local schemas — Phase 1B, 14 November 2026

Both files decode as UTF-8 (the reader tolerates a BOM), using comma delimiters and
standard CSV quoting. Counts exclude headers. Blank means empty or whitespace-only;
null-like literal tokens are counted separately. Checksums are in `data-profile.json`
and `data-quality.json`; the latter verifies identical hashes before and after reading.
Original files were not modified. No source URL values are shown in these reports.

### Jobs: 17,880 rows, 18 columns, 50,061,601 bytes

| Actual column | Observed values / proposed staging type | Blank cells | Use |
| --- | --- | ---: | --- |
| job_id | Integer-compatible / INT64 | 0 | Unique source key |
| title | Text / STRING | 0 | Job label |
| location | Text / STRING | 346 | Derive geography; preserve original |
| department | Mixed text, some numeric-looking / STRING | 11,553 | Optional dimension |
| salary_range | Mixed range text / STRING | 15,012 | Optional safe parsing of bounds |
| company_profile | Text / STRING | 3,308 | Descriptive context |
| description | Text / STRING | 1 | Descriptive context |
| requirements | Text / STRING | 2,696 | Descriptive context |
| benefits | Text / STRING | 7,214 | Descriptive context |
| telecommuting | Only 0/1 / BOOL after explicit mapping | 0 | Optional dimension |
| has_company_logo | Only 0/1 / BOOL after explicit mapping | 0 | Optional dimension |
| has_questions | Only 0/1 / BOOL after explicit mapping | 0 | Optional dimension |
| employment_type | Text / STRING | 3,471 | Fraud-summary dimension |
| required_experience | Text / STRING | 7,050 | Optional dimension |
| required_education | Text / STRING | 8,105 | Optional dimension |
| industry | Text / STRING | 4,903 | Fraud-summary dimension |
| function | Text / STRING | 6,455 | Optional dimension |
| fraudulent | Only 0/1 / BOOL after explicit mapping | 0 | Existing dataset label, counts and percentages |

Observed IDs (at most five digits) and flags fit INT64. These are proposed staging
types, not an assertion about Airbyte's future inferred schema. Keep raw strings where
needed to avoid lossy inference. The CSV format itself has no native data types.

### Phishing: 45,680 rows, 8 columns, 8,795,146 bytes

| Actual column | Observed values / proposed staging type | Blank cells | Use |
| --- | --- | ---: | --- |
| phish_id | Integer-compatible, at most seven digits / INT64 | 0 | Unique report key |
| url | Text / STRING | 0 | Private original; optional offline hostname extraction |
| phish_detail_url | Text / STRING | 0 | Source reference; do not follow links |
| submission_time | Timezone-aware ISO timestamp / TIMESTAMP | 0 | Daily report counts |
| verified | Only yes / BOOL after explicit yes/no mapping | 0 | Report status |
| verification_time | Timezone-aware ISO timestamp / TIMESTAMP | 0 | Verification timing |
| online | Only yes / BOOL after explicit yes/no mapping | 0 | Snapshot status |
| target | Text, 92 distinct trimmed values / STRING | 0 | Top targets |

All values in each timestamp column parse with timezone offsets. Submission range:
2012-06-14 15:19:26 UTC through 2026-11-13 21:02:46 UTC. Verification range:
2012-06-14 15:29:11 UTC through 2026-11-13 21:12:03 UTC. No verification precedes
submission. Record dates do not establish download time or current online status.

## Quality findings and dbt choices

- Both sources have zero blank IDs, duplicate IDs (also checked after trimming), exact
  duplicate rows, malformed-width rows, NUL-containing cells or embedded-newline cells.
  Column names are nonblank and unique. Entire files were inspected, not sampled.
- Jobs have 281 repeated records beyond the first occurrence when comparing all fields
  except `job_id`. Retain distinct IDs initially and flag repeated content for review;
  separate postings may have identical content. Deduplicate repeated ingestions by ID.
- Job labels: 866 fraudulent and 17,014 non-fraudulent, or approximately 4.84% fraudulent
  in this dataset. This is a source label summary, not a model prediction or population estimate.
- Outer whitespace occurs in title (2,202), location (2,000), department (229),
  company_profile (1,991), description (3,525), requirements (2,233) and benefits (1,256).
  Preserve raw data and trim in staging.
- Null-like literal tokens occur in description (1), requirements (2) and benefits (7),
  using the case-insensitive set `null`, `none`, `nan`, `n/a`, `na`. These are separate
  from blank counts. Review token meaning before converting to NULL.
- Salary is blank in 15,012 rows (83.96%). Of 2,868 nonblank values, 27 fail a simple
  integer `lower-upper` pattern; no matching range has lower > upper. Do not infer
  currency/period. Preserve original text and use safe parsing for optional bounds.
- Of 17,534 nonblank locations, 214 have other than three comma-separated parts.
  Even three-part values require semantic review. Keep original location and an Unknown
  group for missing/unparseable geography rather than blindly splitting every record.
- Phishing has 45,678 distinct trimmed URLs for 45,680 IDs: two repeated values beyond
  their first occurrence. Report totals and distinct-URL totals differ. Deduplicate reports
  by `phish_id`, not URL. There is no repeated full content excluding the ID.
- Both URL columns pass a limited offline HTTP(S)-scheme/hostname structure check.
  This is neither network validation nor a safety judgment. Eight reported URLs contain
  userinfo; parse hostnames with a URL parser rather than splitting on `@` or `/`.
- All phishing statuses are `yes`. Do not infer safe or offline counts from this filtered
  historical snapshot, or join these reports to job records without a defensible relationship.

For `mart_job_fraud_summary`, prioritize ID, label and location, then employment type and
industry. For `mart_phishing_summary`, prioritize report ID, submission date, target and
status. Later dbt tests should check unique/not-null IDs, accepted flag values, safe casts,
timestamp parsing and chronology. Sparse optional job fields should remain nullable.

## Airbyte considerations from the actual files

- No Python CSV structural blocker was found. Actual connector discovery and sync remain
  untested; local readability does not prove Airbyte compatibility or worker file access.
- The longest reported URL is 25,523 characters/UTF-8 bytes. Job description reaches
  14,907 characters and 22,722 UTF-8 bytes. Check for inference/preview truncation and
  length assumptions in the selected connector and destination; preserve complete strings.
- Mixed salary text and numeric-looking departments should remain STRING. Review discovered
  schemas instead of trusting sample-based type inference. Review blank-to-null conversion,
  Unicode preservation, 0/1 and yes/no mappings and timestamps with timezone offsets.
- Static CSV snapshots lack a job update timestamp. Plan an intentional full refresh for
  initial loading and verify connector modes later; repeated append runs can duplicate data.
- Choose a verified connector-accessible file location; Windows paths are not automatically
  visible to workers. Keep two separate sources/connections. Record snapshot checksums,
  download times, license/usage terms and any preparation steps; these provenance details
  are still needed beyond the user's confirmation of successful downloads.
