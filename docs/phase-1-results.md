# Phase 1 and Phase 1B verification

Inspection date: 14 November 2026, Asia/Calcutta. Phase 1B supersedes the initial
missing-dataset result. Both user-provided local snapshots now read successfully.

| Check | Job postings | Phishing reports |
| --- | ---: | ---: |
| Bytes | 50,061,601 | 8,795,146 |
| Data rows | 17,880 | 45,680 |
| Columns | 18 | 8 |
| Blank IDs | 0 | 0 |
| Duplicate IDs, also checked after trimming | 0 | 0 |
| Exact duplicate rows | 0 | 0 |
| Malformed-width rows | 0 | 0 |
| Repeated content excluding ID, beyond first occurrence | 281 | 0 |

Both CSVs were fully read as UTF-8 with BOM tolerance, without decoding or CSV errors.
Headers are nonblank and unique. Before/after SHA-256 checks match; originals were not
modified. Full hashes are recorded in `data-profile.json` and `data-quality.json`.

Jobs have sparse optional fields, whitespace, 10 null-like literal cells, 27 nonstandard
nonblank salary ranges and 214 nonblank locations with other than three comma-separated
parts. Labels: 866 fraudulent and 17,014 non-fraudulent (approximately 4.84% fraudulent).

Phishing has no blank cells, 92 distinct targets and all status values `yes`. There are
45,678 distinct URLs, eight URLs containing userinfo and a maximum URL length of 25,523
characters. No source URL values were printed or visited. All timestamps parse with
timezone offsets; none has verification before submission. Offline URL structure checks
are not safety checks or proof of current live status.

## Commands and results

Run from the project folder in PowerShell:

- `python scripts/inspect_data.py --self-test` — exit 0. Temporary synthetic fixtures
  check BOM, quoted commas, duplicates, malformed widths, duplicate headers, empty and
  missing files. They do not replace or modify the real datasets.
- `python scripts/inspect_data.py` — exit 0. Existing inspector fully reads real files
  and updates `docs/data-profile.json`: headers, rows, blank counts, keys and checksums.
- `python scripts/inspect_quality.py` — exit 0. New standard-library inspector writes
  `docs/data-quality.json`: type-compatibility counts, flags, timestamps, whitespace,
  lengths and repeated content. Source hashes are verified before and after reading.

No additional test suite/configuration was found in the workspace. The existing
inspector self-tests are the available fixture suite. No dependencies were installed.

## Remaining issues and scope

See `data-preparation.md` for all verified columns, proposed types, missing counts,
dbt choices and Airbyte considerations. No local CSV structural blocker remains.
Download timestamps, original download filenames, license/usage terms and any prior
preparation steps still need a provenance record. The user reports successful downloads;
the inspector does not authenticate their acquisition history.

Airbyte worker access, discovered schemas, long-string handling and real sync success
remain untested. No cloud actions, services, SQL models, screenshots or ingestion results
were created. Git is installed; the folder was not initialized as a repository.
BigQuery setup has not begun. Phase 2 requires explicit user approval.
