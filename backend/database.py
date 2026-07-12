import sqlite3
import os

DATABASE = os.environ.get("RIGHT_EWASTE_DATABASE", os.path.join(
    os.path.dirname(__file__),
    "..",
    "database",
    "erp.db"
))

def get_connection():
    conn = sqlite3.connect(DATABASE, timeout=10)
    conn.row_factory = sqlite3.Row
    # SQLite does not enforce foreign keys unless every connection enables it.
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 10000")
    return conn
