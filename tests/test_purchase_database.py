import sqlite3
import unittest
from pathlib import Path

from backend import database


class PurchaseDatabaseInitTest(unittest.TestCase):
    def test_initialize_database_creates_purchase_tables(self):
        database.initialize_database()

        conn = sqlite3.connect(Path("database/erp.db"))
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('purchase_invoice', 'purchase_invoice_item')"
            )
            tables = {row[0] for row in cur.fetchall()}
        finally:
            conn.close()

        self.assertEqual(tables, {"purchase_invoice", "purchase_invoice_item"})


if __name__ == "__main__":
    unittest.main()
