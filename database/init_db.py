"""Create the SQLite schema for a new Right Ewaste ERP database."""

import argparse
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SCHEMA_DIR = ROOT / "schema"


def initialise(database_path: Path) -> None:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        for schema_file in sorted(SCHEMA_DIR.glob("*.sql")):
            sql = schema_file.read_text(encoding="utf-8")
            connection.executescript(sql.replace("CREATE TABLE ", "CREATE TABLE IF NOT EXISTS ", 1))
    print(f"Database ready: {database_path.resolve()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, default=ROOT / "erp.db")
    args = parser.parse_args()
    initialise(args.database)
