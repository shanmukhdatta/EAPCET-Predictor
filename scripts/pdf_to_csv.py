"""
pdf_to_csv.py

Converts an official AP EAPCET "Last Rank Details" PDF into a clean CSV file.

Usage:
    python scripts/pdf_to_csv.py --year 2024
    python scripts/pdf_to_csv.py --year 2025 --pdf data/pdfs/2025/my_file.pdf

How it works:
    The source PDF has one large table per page (SNO, INSTCODE, college name,
    type, district, place, affiliation, branch code, then 18 rank-cutoff
    columns for every category x gender combination, then college fee).
    Some cells wrap onto a second line inside the PDF (e.g. a long place name
    like "PEDDAPURAM" prints as "PEDDAPURA" / "M" on two lines within the same
    cell). pdfplumber's extract_tables() keeps each PDF cell intact (joining
    wrapped lines with \\n), which is far more reliable than guessing row
    boundaries from raw text. We then:
        1. Pull every table cell, page by page.
        2. Collapse internal newlines into single spaces.
        3. Re-join PLACE names that were split mid-word across two lines
           (a known PDF quirk for long town names).
        4. Write everything to a year-stamped CSV.

To add a new year: drop the official PDF into data/pdfs/<year>/ and run
this script with --year <year>. No code changes needed unless the PDF's
column layout differs from the 2024 format.
"""

import argparse
import csv
import re
import sys
from pathlib import Path

import pdfplumber

# Column order matches the source PDF's table layout exactly.
HEADERS = [
    "SNO", "INSTCODE", "NAME_OF_INSTITUTION", "TYPE", "INST_REG", "DIST", "PLACE",
    "COED", "AFFL", "ESTD", "A_REG", "BRANCH_CODE",
    "EWS_BOYS", "EWS_GIRLS", "OC_BOYS", "OC_GIRLS", "SC_BOYS", "SC_GIRLS",
    "ST_BOYS", "ST_GIRLS", "BCA_BOYS", "BCA_GIRLS", "BCB_BOYS", "BCB_GIRLS",
    "BCC_BOYS", "BCC_GIRLS", "BCD_BOYS", "BCD_GIRLS", "BCE_BOYS", "BCE_GIRLS",
    "COLLEGE_FEE",
]

EXPECTED_COLS = len(HEADERS)

# Pattern for a place name that was wrapped across two lines inside one PDF
# cell, e.g. "PEDDAPURA M" (joined with a space after newline-collapse) which
# should really read "PEDDAPURAM". We only merge when the second fragment is
# short (<=3 letters) and alphabetic, which matches the real-world wrapping
# pattern seen in these documents and avoids merging genuinely two-word place
# names (e.g. "RAMPACHODAVARAM" stays separate if both halves are longer).
SPLIT_PLACE_RE = re.compile(r"^([A-Z]+)\s([A-Z]{1,3})$")


def clean_cell(value):
    """Collapse internal newlines/whitespace from a wrapped PDF cell."""
    if value is None:
        return ""
    return " ".join(str(value).split())


def fix_place(place):
    """Re-join a place name that was split mid-word across PDF lines."""
    m = SPLIT_PLACE_RE.match(place)
    if m:
        return m.group(1) + m.group(2)
    return place


def extract_rows(pdf_path: Path):
    rows = []
    skipped = 0
    with pdfplumber.open(str(pdf_path)) as pdf:
        total_pages = len(pdf.pages)
        for pnum, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables()
            for table in tables:
                for raw_row in table:
                    if not raw_row or not raw_row[0]:
                        continue
                    sno = str(raw_row[0]).strip()
                    if not sno.isdigit():
                        # Header row or stray text row, skip.
                        continue
                    cleaned = [clean_cell(c) for c in raw_row]
                    if len(cleaned) != EXPECTED_COLS:
                        print(
                            f"  [warn] page {pnum}: row SNO={sno} has "
                            f"{len(cleaned)} columns, expected {EXPECTED_COLS}. Skipped.",
                            file=sys.stderr,
                        )
                        skipped += 1
                        continue
                    cleaned[6] = fix_place(cleaned[6])  # PLACE column
                    rows.append(cleaned)
            if pnum % 10 == 0 or pnum == total_pages:
                print(f"  processed page {pnum}/{total_pages}")
    return rows, skipped


def main():
    parser = argparse.ArgumentParser(description="Convert an EAPCET rank-details PDF to CSV.")
    parser.add_argument("--year", required=True, help="Admission year, e.g. 2024")
    parser.add_argument(
        "--pdf",
        default=None,
        help="Path to the source PDF. Defaults to the first PDF found in "
        "data/pdfs/<year>/",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Output CSV path. Defaults to data/csv/eapcet_<year>.csv",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    pdf_dir = root / "data" / "pdfs" / args.year

    if args.pdf:
        pdf_path = Path(args.pdf)
    else:
        candidates = sorted(pdf_dir.glob("*.pdf"))
        if not candidates:
            print(f"No PDF found in {pdf_dir}. Place a PDF there or pass --pdf.", file=sys.stderr)
            sys.exit(1)
        pdf_path = candidates[0]

    if not pdf_path.exists():
        print(f"PDF not found: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    out_path = Path(args.out) if args.out else root / "data" / "csv" / f"eapcet_{args.year}.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Reading: {pdf_path}")
    rows, skipped = extract_rows(pdf_path)

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(HEADERS)
        writer.writerows(rows)

    print(f"\nDone. {len(rows)} rows written, {skipped} rows skipped.")
    print(f"CSV saved to: {out_path}")


if __name__ == "__main__":
    main()
