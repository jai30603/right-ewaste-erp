import sqlite3
import os

DATABASE = os.path.join(
    os.path.dirname(__file__),
    "..",
    "database",
    "erp.db"
)

print("Database Path:", os.path.abspath(DATABASE))

def get_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn