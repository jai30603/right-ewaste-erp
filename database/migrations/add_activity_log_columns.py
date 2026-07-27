"""Migration: Add extended columns to activity_log if not present."""
import sqlite3
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))


def migrate(conn):
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(activity_log)")
    existing = {row[1] for row in cursor.fetchall()}

    new_cols = [
        ("session_id", "TEXT"),
        ("record_id", "TEXT"),
        ("before_value", "TEXT"),
        ("after_value", "TEXT"),
        ("severity", "TEXT DEFAULT 'INFO'"),
    ]
    for col_name, col_def in new_cols:
        if col_name not in existing:
            cursor.execute(f"ALTER TABLE activity_log ADD COLUMN {col_name} {col_def}")
            print(f"Added column: {col_name}")
        else:
            print(f"Column already exists: {col_name}")

    conn.commit()
    print("Migration complete.")


if __name__ == "__main__":
    DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'erp.db')
    conn = sqlite3.connect(DB_PATH)
    migrate(conn)
    conn.close()
