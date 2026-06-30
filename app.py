"""
app.py

Flask backend for the AP EAPCET College Predictor.

Serves:
    GET  /                          -> the single-page predictor UI
    GET  /api/meta                  -> filter options (years, districts, branches)
    GET  /api/predict               -> college predictions for a given rank/category/etc.
    GET  /healthz                   -> health check (used by hosting platforms)

Run locally:
    pip install -r requirements.txt
    python scripts/csv_to_db.py        # build the database once
    python app.py
    -> open http://localhost:5000

Deploy (Render free tier, single service):
    Start command:  gunicorn app:app
    The SQLite file at data/db/eapcet.db ships inside the repo, so no
    separate database service is needed.
"""

import sqlite3
from pathlib import Path

from flask import Flask, g, jsonify, render_template, request

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "db" / "eapcet.db"

app = Flask(__name__)

# Maps the category value the frontend sends to the actual column-name prefix
# stored in the database. Keeping this server-side means the frontend never
# needs to know SQL column names.
CATEGORY_PREFIXES = {
    "EWS": "ews",
    "OC": "oc",
    "SC": "sc",
    "ST": "st",
    "BCA": "bca",
    "BCB": "bcb",
    "BCC": "bcc",
    "BCD": "bcd",
    "BCE": "bce",
}

GENDER_SUFFIXES = {
    "boys": "boys",
    "girls": "girls",
}


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(str(DB_PATH))
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/healthz")
def healthz():
    return jsonify(status="ok")


@app.route("/api/meta")
def meta():
    """Returns the distinct values available for each filter, so the
    frontend dropdowns are always in sync with whatever years/data are
    actually loaded in the database."""
    db = get_db()

    years = [r["year"] for r in db.execute(
        "SELECT DISTINCT year FROM colleges ORDER BY year DESC"
    )]

    districts = [dict(r) for r in db.execute(
        """SELECT DISTINCT dist AS code FROM colleges
           WHERE dist IS NOT NULL AND dist != '' ORDER BY dist"""
    )]

    branches = [dict(r) for r in db.execute(
        """SELECT DISTINCT branch_code AS code FROM colleges
           WHERE branch_code IS NOT NULL AND branch_code != '' ORDER BY branch_code"""
    )]

    colleges = [dict(r) for r in db.execute(
        """SELECT instcode AS code, MIN(name_of_institution) AS name FROM colleges
           WHERE instcode IS NOT NULL AND instcode != ''
           GROUP BY instcode
           ORDER BY instcode"""
    )]

    return jsonify(
        years=years,
        categories=list(CATEGORY_PREFIXES.keys()),
        genders=list(GENDER_SUFFIXES.keys()),
        districts=districts,
        branches=branches,
        colleges=colleges,
    )


@app.route("/api/predict")
def predict():
    """
    Query params:
        rank      (required) integer, the candidate's EAPCET rank
        category  (required) one of CATEGORY_PREFIXES keys, e.g. "OC"
        gender    (required) "boys" or "girls"
        year      (optional) admission year, defaults to the latest year present
        district  (optional) district code, "ALL" or omitted = no filter
        branch    (optional) branch code, "ALL" or omitted = no filter

    Returns colleges where the candidate's rank is within the closing rank
    for that category/gender/branch, ordered by closing rank ascending
    (closest cutoff to the candidate's rank first) so the most realistic
    options appear at the top.
    """
    rank_raw = request.args.get("rank", "").strip()
    category = request.args.get("category", "").strip().upper()
    gender = request.args.get("gender", "").strip().lower()
    year = request.args.get("year", "").strip()
    district = request.args.get("district", "ALL").strip()
    branch = request.args.get("branch", "ALL").strip()
    college = request.args.get("college", "ALL").strip()

    if not rank_raw.isdigit():
        return jsonify(error="Please enter a valid numeric rank."), 400
    rank = int(rank_raw)

    if category not in CATEGORY_PREFIXES:
        return jsonify(error=f"Unknown category '{category}'."), 400
    if gender not in GENDER_SUFFIXES:
        return jsonify(error=f"Unknown gender '{gender}'."), 400

    column = f"{CATEGORY_PREFIXES[category]}_{GENDER_SUFFIXES[gender]}"

    db = get_db()

    if not year:
        row = db.execute("SELECT MAX(year) AS y FROM colleges").fetchone()
        year = row["y"]
    else:
        if not year.isdigit():
            return jsonify(error="Year must be numeric."), 400
        year = int(year)

    where = [f"{column} IS NOT NULL", f"{column} >= ?", "year = ?"]
    params = [rank, year]

    if district and district != "ALL":
        where.append("dist = ?")
        params.append(district)

    if branch and branch != "ALL":
        where.append("branch_code = ?")
        params.append(branch)

    if college and college != "ALL":
        where.append("instcode = ?")
        params.append(college)

    sql = f"""
        SELECT
            name_of_institution, instcode, type, dist, place, affl, estd,
            branch_code, college_fee, {column} AS closing_rank
        FROM colleges
        WHERE {' AND '.join(where)}
        ORDER BY closing_rank ASC
        LIMIT 200
    """

    rows = [dict(r) for r in db.execute(sql, params)]

    return jsonify(
        year=year,
        category=category,
        gender=gender,
        rank=rank,
        district=district,
        branch=branch,
        college=college,
        count=len(rows),
        results=rows,
    )


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
