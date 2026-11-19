#!/usr/bin/env python3
"""Build the SQLite database from the CSV files in ../data.

Usage:  python3 backend/import_csv.py

Every CSV becomes a table (column types are inferred), then the working `acts`
table is assembled from the act summary and the train/test split. Standard
library only, so it runs anywhere Python 3.8+ is installed.
"""
import csv
import json
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DB_PATH = ROOT / "database" / "act_reactions.db"

# table name -> source CSV in data/
SOURCES = {
    "act_summary": "act_level_summary.csv",
    "act_split": "act_split_and_targets.csv",
    "model_regression": "model_comparison_regression.csv",
    "model_classification": "model_comparison_classification.csv",
    "test_predictions": "test_predictions.csv",
    "neighbors": "neighbors_top5.csv",
}
DERIVED = {
    "acts": "act_summary + act_split (editable working copy)",
    "run_info": "run_info.json",
    "scenarios": "saved in the Policy simulator",
    "v_jurisdiction_summary": "view over acts",
    "v_domain_summary": "view over acts",
}


def clean(header):
    return re.sub(r"\W+", "_", header.strip()).strip("_")


def infer(values):
    values = [v for v in values if v != ""]
    if not values:
        return "TEXT"
    try:
        for v in values:
            int(v)
        return "INTEGER"
    except ValueError:
        pass
    try:
        for v in values:
            float(v)
        return "REAL"
    except ValueError:
        return "TEXT"


def load_csv(con, table, path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        head = [clean(h) for h in next(reader)]
        rows = list(reader)
    types = [infer([r[i] for r in rows]) for i in range(len(head))]
    cols = ", ".join(f'"{h}" {t}' for h, t in zip(head, types))
    con.execute(f'CREATE TABLE "{table}" ({cols})')
    marks = ",".join("?" * len(head))
    con.executemany(
        f'INSERT INTO "{table}" VALUES ({marks})',
        [[(None if v == "" else v) for v in r] for r in rows],
    )
    return len(rows)


ACTS_SQL = """
CREATE TABLE acts (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  year INTEGER,
  jurisdiction TEXT,
  department TEXT,
  ministry TEXT,
  level TEXT,
  n_total INTEGER DEFAULT 0,
  n_relevant INTEGER DEFAULT 0,
  n_negative INTEGER DEFAULT 0,
  n_neutral INTEGER DEFAULT 0,
  n_positive INTEGER DEFAULT 0,
  net_sentiment REAL,
  net_sentiment_shrunk REAL,
  polarisation REAL,
  dominant TEXT,
  mean_confidence REAL,
  reliable INTEGER DEFAULT 0,
  tier TEXT,
  domain TEXT,
  act_type TEXT,
  split TEXT,
  split_date TEXT,
  strict_test INTEGER DEFAULT 0
);
INSERT INTO acts
SELECT s.Research_ID, s.Title, s.Year, s.Jurisdiction, s.Department, s.Ministry, s.Level,
       s.n_total, s.n_relevant, s.n_Negative, s.n_Neutral, s.n_Positive,
       s.net_sentiment, s.net_sentiment_shrunk, s.polarisation, s.dominant, s.mean_sent_conf,
       CASE WHEN s.reliable_adj IN ('True','true','1') THEN 1 ELSE 0 END,
       s.tier_total, s.domain, s.act_type, p.split, p.date,
       CASE WHEN p.strict IN ('True','true','1') THEN 1 ELSE 0 END
FROM act_summary s LEFT JOIN act_split p ON p.Research_ID = s.Research_ID;

CREATE INDEX idx_acts_jurisdiction ON acts(jurisdiction);
CREATE INDEX idx_acts_domain ON acts(domain);
CREATE INDEX idx_acts_year ON acts(year);
CREATE INDEX idx_neighbors_act ON neighbors(act_id);

CREATE TABLE scenarios (
  id INTEGER PRIMARY KEY,
  title TEXT NOT NULL,
  jurisdiction TEXT,
  domain TEXT,
  act_type TEXT,
  year INTEGER,
  expected_net REAL,
  similar_net REAL,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE VIEW v_jurisdiction_summary AS
SELECT jurisdiction, COUNT(*) AS acts, SUM(n_total) AS reactions, SUM(n_relevant) AS relevant_reactions,
       ROUND(1.0 * (SUM(n_positive) - SUM(n_negative)) / NULLIF(SUM(n_relevant), 0), 3) AS net_sentiment
FROM acts GROUP BY jurisdiction;

CREATE VIEW v_domain_summary AS
SELECT domain, COUNT(*) AS acts, SUM(n_total) AS reactions, SUM(n_relevant) AS relevant_reactions,
       ROUND(1.0 * (SUM(n_positive) - SUM(n_negative)) / NULLIF(SUM(n_relevant), 0), 3) AS net_sentiment
FROM acts GROUP BY domain;
"""


def build(verbose=False):
    DB_PATH.parent.mkdir(exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
    con = sqlite3.connect(DB_PATH)
    for table, fname in SOURCES.items():
        n = load_csv(con, table, DATA / fname)
        if verbose:
            print(f"  {table:22s} {n:6d} rows  <- {fname}")
    con.execute("CREATE TABLE run_info (key TEXT PRIMARY KEY, value TEXT)")
    info = json.loads((DATA / "run_info.json").read_text())
    con.executemany("INSERT INTO run_info VALUES (?, ?)", [(k, json.dumps(v)) for k, v in info.items()])
    con.executescript(ACTS_SQL)
    con.commit()
    con.close()


if __name__ == "__main__":
    print(f"Building {DB_PATH} ...")
    build(verbose=True)
    print("Done.")
