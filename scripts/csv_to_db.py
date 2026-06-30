"""
csv_to_db.py

Loads one or more year CSV files (produced by pdf_to_csv.py) into a single
SQLite database, with proper integer typing on rank/fee columns so the
predictor can do numeric comparisons.

Usage:
    python scripts/csv_to_db.py                  # loads every CSV in data/csv/
    python scripts/csv_to_db.py --csv data/csv/eapcet_2024.csv
    python scripts/csv_to_db.py --rebuild         # drops and recreates tables first

Schema:
    colleges        one row per (year, college, branch) combination, with the
                    18 category/gender rank-cutoff columns as INTEGER (NULL if
                    that category/gender had no allotment that year).
    colleges_meta   distinct list of (year, district, branch) etc. for
                    populating filter dropdowns quickly without scanning the
                    full table.

Re-running is safe: rows are keyed by (YEAR, SNO) so re-importing the same
year's CSV replaces that year's data rather than duplicating it.
"""

import argparse
import csv
import sqlite3
import sys
from pathlib import Path

RANK_COLUMNS = [
    "EWS_BOYS", "EWS_GIRLS", "OC_BOYS", "OC_GIRLS", "SC_BOYS", "SC_GIRLS",
    "ST_BOYS", "ST_GIRLS", "BCA_BOYS", "BCA_GIRLS", "BCB_BOYS", "BCB_GIRLS",
    "BCC_BOYS", "BCC_GIRLS", "BCD_BOYS", "BCD_GIRLS", "BCE_BOYS", "BCE_GIRLS",
]

TEXT_COLUMNS = [
    "INSTCODE", "NAME_OF_INSTITUTION", "TYPE", "INST_REG", "DIST", "PLACE",
    "COED", "AFFL", "A_REG", "BRANCH_CODE",
]

CREATE_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS colleges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    year INTEGER NOT NULL,
    sno INTEGER NOT NULL,
    instcode TEXT NOT NULL,
    name_of_institution TEXT NOT NULL,
    type TEXT,
    inst_reg TEXT,
    dist TEXT,
    place TEXT,
    coed TEXT,
    affl TEXT,
    estd INTEGER,
    a_reg TEXT,
    branch_code TEXT NOT NULL,
    {", ".join(c.lower() + " INTEGER" for c in RANK_COLUMNS)},
    college_fee INTEGER,
    UNIQUE(year, sno)
);
"""

INDEX_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_colleges_year ON colleges(year);",
    "CREATE INDEX IF NOT EXISTS idx_colleges_dist ON colleges(dist);",
    "CREATE INDEX IF NOT EXISTS idx_colleges_branch ON colleges(branch_code);",
    "CREATE INDEX IF NOT EXISTS idx_colleges_instcode ON colleges(instcode);",
]


def to_int(value):
    """Convert a CSV cell to int, or None if blank/non-numeric."""
    value = (value or "").strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def load_csv(conn: sqlite3.Connection, csv_path: Path):
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        print(f"  [warn] {csv_path} has no data rows, skipping.")
        return 0

    # Infer year from filename, e.g. eapcet_2024.csv -> 2024
    stem = csv_path.stem
    year = None
    for token in stem.replace("-", "_").split("_"):
        if token.isdigit() and len(token) == 4:
            year = int(token)
            break
    if year is None:
        print(f"  [error] could not infer year from filename '{csv_path.name}'. "
              f"Expected something like eapcet_2024.csv.", file=sys.stderr)
        return 0

    # Remove any existing rows for this year so re-imports don't duplicate.
    conn.execute("DELETE FROM colleges WHERE year = ?", (year,))

    insert_cols = (
        ["year", "sno"]
        + [c.lower() for c in TEXT_COLUMNS if c not in RANK_COLUMNS]
        + ["estd"]
        + [c.lower() for c in RANK_COLUMNS]
        + ["college_fee"]
    )
    # Build column list precisely in the order we'll supply values.
    insert_cols = [
        "year", "sno", "instcode", "name_of_institution", "type", "inst_reg",
        "dist", "place", "coed", "affl", "estd", "a_reg", "branch_code",
    ] + [c.lower() for c in RANK_COLUMNS] + ["college_fee"]

    placeholders = ", ".join("?" for _ in insert_cols)
    insert_sql = f"INSERT INTO colleges ({', '.join(insert_cols)}) VALUES ({placeholders})"

    count = 0
    for row in rows:
        values = [
            year,
            to_int(row["SNO"]),
            row["INSTCODE"].strip(),
            row["NAME_OF_INSTITUTION"].strip(),
            row["TYPE"].strip(),
            row["INST_REG"].strip(),
            row["DIST"].strip(),
            row["PLACE"].strip(),
            row["COED"].strip(),
            row["AFFL"].strip(),
            to_int(row["ESTD"]),
            row["A_REG"].strip(),
            row["BRANCH_CODE"].strip(),
        ] + [to_int(row[c]) for c in RANK_COLUMNS] + [to_int(row["COLLEGE_FEE"])]
        conn.execute(insert_sql, values)
        count += 1

    conn.commit()
    print(f"  loaded {count} rows for year {year} from {csv_path.name}")
    return count


def main():
    parser = argparse.ArgumentParser(description="Load EAPCET CSV file(s) into SQLite.")
    parser.add_argument("--csv", default=None, help="Path to a single CSV. Default: load every CSV in data/csv/")
    parser.add_argument("--db", default=None, help="Path to the SQLite database file.")
    parser.add_argument("--rebuild", action="store_true", help="Drop and recreate the colleges table first.")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    db_path = Path(args.db) if args.db else root / "data" / "db" / "eapcet.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL;")

    if args.rebuild:
        conn.execute("DROP TABLE IF EXISTS colleges;")
        print("Dropped existing colleges table.")

    conn.execute(CREATE_TABLE_SQL)
    for stmt in INDEX_SQL:
        conn.execute(stmt)

    if args.csv:
        csv_paths = [Path(args.csv)]
    else:
        csv_dir = root / "data" / "csv"
        csv_paths = sorted(csv_dir.glob("*.csv"))
        if not csv_paths:
            print(f"No CSV files found in {csv_dir}.", file=sys.stderr)
            sys.exit(1)

    total = 0
    for csv_path in csv_paths:
        if not csv_path.exists():
            print(f"  [error] CSV not found: {csv_path}", file=sys.stderr)
            continue
        total += load_csv(conn, csv_path)

    row_count = conn.execute("SELECT COUNT(*) FROM colleges").fetchone()[0]
    year_count = conn.execute("SELECT COUNT(DISTINCT year) FROM colleges").fetchone()[0]
    conn.close()

    print(f"\nDone. {total} rows imported this run.")
    print(f"Database now has {row_count} total rows across {year_count} year(s).")
    print(f"Database saved to: {db_path}")


if __name__ == "__main__":
    main()
