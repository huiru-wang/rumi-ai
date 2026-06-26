#!/usr/bin/env python3
"""Execute raw SQL against the RumiAI SQLite database.

Usage:
    python scripts/run_sql.py "SELECT * FROM workspace LIMIT 5;"
    python scripts/run_sql.py "UPDATE workspace SET ext_data='{}' WHERE id=1;"
    echo "SELECT count(*) FROM message;" | python scripts/run_sql.py
"""

import os
import sys
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "backend", "data", "rumi_ai.db")


def main():
    # Read SQL from argv or stdin
    if len(sys.argv) > 1:
        sql = " ".join(sys.argv[1:])
    elif not sys.stdin.isatty():
        sql = sys.stdin.read().strip()
    else:
        print(__doc__)
        sys.exit(1)

    if not sql:
        print("Error: empty SQL", file=sys.stderr)
        sys.exit(1)

    db_path = os.path.normpath(DB_PATH)
    if not os.path.exists(db_path):
        print(f"Error: database not found at {db_path}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    try:
        cur.execute(sql)
        if cur.description:
            # SELECT — print results as table
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description]
            print("\t".join(cols))
            print("-" * (len(cols) * 15))
            for row in rows:
                print("\t".join(str(v) for v in row))
            print(f"\n({len(rows)} row(s))")
        else:
            conn.commit()
            print(f"OK — {cur.rowcount} row(s) affected")
    except sqlite3.Error as e:
        print(f"SQL Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
