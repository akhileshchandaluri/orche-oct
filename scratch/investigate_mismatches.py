import csv
import json
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path("d:/btech/projects/orchestrate/orchestrate oct/hackerrank-orchestrate-october26")
DATASET_DIR = PROJECT_ROOT / "dataset"

terms = ['audit_record_6645', 'audit_record_5569', 'account_3136', 'analytics_1895', 'account_5684', 'analytics_4566', 'account_3866', 'analytics_4574', 'account_5482', 'analytics_6077']

print("--- Searching SQLite files ---")
for p in DATASET_DIR.rglob("*.db"):
    try:
        conn = sqlite3.connect(p)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        for (tbl,) in cur.fetchall():
            cur.execute(f"SELECT * FROM {tbl}")
            for row in cur.fetchall():
                row_str = str(row)
                for t in terms:
                    if t in row_str:
                        print(f"Found {t} in {p.name} [{tbl}]")
    except Exception as e:
        pass

for p in DATASET_DIR.rglob("*.sqlite"):
    try:
        conn = sqlite3.connect(p)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        for (tbl,) in cur.fetchall():
            cur.execute(f"SELECT * FROM {tbl}")
            for row in cur.fetchall():
                row_str = str(row)
                for t in terms:
                    if t in row_str:
                        print(f"Found {t} in {p.name} [{tbl}]")
    except Exception as e:
        pass

print("--- Searching user_audit_log and identities ---")
for p in [DATASET_DIR / "user_audit_log.csv", DATASET_DIR / "user_identities.csv", DATASET_DIR / "system_activity.csv"]:
    if p.exists():
        with open(p, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                for t in terms:
                    if t in line:
                        print(f"Found {t} in {p.name}:L{line_no}")
