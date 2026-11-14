"""Offline CSV profiling. No network access or third-party dependencies."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {"jobs": ("fake_job_postings.csv", "job_id"),
           "phishing": ("phishing_reports.csv", "phish_id")}


def profile(path, key):
    result = {"file": path.name, "status": "missing"}
    if not path.is_file():
        return result
    try:
        digest = hashlib.sha256()
        with path.open("rb") as binary:
            for chunk in iter(lambda: binary.read(1024 * 1024), b""):
                digest.update(chunk)
        result["sha256"] = digest.hexdigest()
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle, strict=True)
            columns = next(reader, [])
            errors = []
            if not columns or any(not c.strip() for c in columns):
                errors.append("Missing or blank column names")
            if len(columns) != len(set(columns)):
                errors.append("Duplicate column names")
            rows = malformed = duplicates = duplicate_keys = blank_keys = 0
            empty = [0] * len(columns)
            seen, keys = set(), set()
            key_index = columns.index(key) if key in columns else None
            for row in reader:
                rows += 1
                if len(row) != len(columns):
                    malformed += 1
                    continue
                values = tuple(row)
                duplicates += values in seen
                seen.add(values)
                for index, value in enumerate(row):
                    empty[index] += not value.strip()
                if key_index is not None:
                    value = row[key_index].strip()
                    if not value:
                        blank_keys += 1
                    else:
                        duplicate_keys += value in keys
                        keys.add(value)
            if malformed:
                errors.append("Rows have inconsistent column counts")
            if not rows:
                errors.append("No data rows")
            result.update(status="invalid" if errors else "inspected", columns=columns,
                          rows=rows, malformed_rows=malformed, duplicate_rows=duplicates,
                          empty_cells_by_column=dict(zip(columns, empty)),
                          key_column=key if key_index is not None else None,
                          duplicate_keys=duplicate_keys, blank_keys=blank_keys, errors=errors)
    except (OSError, UnicodeError, csv.Error) as exc:
        # Do not echo CSV content or potentially sensitive values from exceptions.
        result.update(status="invalid", errors=[type(exc).__name__])
    return result


def self_test():
    with tempfile.TemporaryDirectory(prefix="scamouflage_synthetic_") as directory:
        path = Path(directory) / "SYNTHETIC_phishing.csv"
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["phish_id", "url", "target"])
            writer.writerow(["TEST-1", "https://fixture.invalid/", "Synthetic, target"])
            writer.writerow(["TEST-1", "https://fixture.invalid/", "Synthetic, target"])
        result = profile(path, "phish_id")
        assert result["status"] == "inspected" and result["rows"] == 2
        assert result["duplicate_rows"] == 1 and result["duplicate_keys"] == 1
        path.write_text("phish_id,url\nTEST-1\n", encoding="utf-8")
        assert profile(path, "phish_id")["status"] == "invalid"
        path.write_text("id,id\n1,2\n", encoding="utf-8")
        assert profile(path, "id")["status"] == "invalid"
        path.write_text("id\n", encoding="utf-8")
        assert profile(path, "id")["status"] == "invalid"
        assert profile(Path(directory) / "absent.csv", "id")["status"] == "missing"
    print("PASS: synthetic-only offline checks (BOM, quoted comma, duplicates, malformed rows, duplicate headers, empty and missing files).")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    results = {name: profile(ROOT / "data" / filename, key)
               for name, (filename, key) in SOURCES.items()}
    output = ROOT / "docs" / "data-profile.json"
    output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results, indent=2))
    print("Saved docs/data-profile.json; no URLs were accessed.")
    return 0 if all(r["status"] == "inspected" for r in results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
