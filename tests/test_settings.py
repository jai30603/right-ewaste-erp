import unittest
import sqlite3
import os
import sys

# Insert backend directory in path so repositories can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from database import get_connection
from repositories import settings_repository
from services import settings_service

class TestSettingsCenter(unittest.TestCase):
    
    def setUp(self):
        # We can run tests on the active database since it uses standard sandbox patterns
        self.conn = get_connection()
        # Seed test number series if not exists
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO number_series (series_key, prefix, suffix, starting_number, current_number, padding_length, reset_yearly, last_reset_year)
            VALUES ('TEST_SERIES', 'TST-', '-OK', 10, 5, 4, 0, 2026)
            ON CONFLICT(series_key) DO NOTHING
        """)
        self.conn.commit()

    def tearDown(self):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM number_series WHERE series_key = 'TEST_SERIES'")
        cursor.execute("DELETE FROM system_setting WHERE setting_key = 'TEST_CONFIG_PARAM'")
        cursor.execute("DELETE FROM material_category WHERE name = 'TestCatX'")
        cursor.execute("DELETE FROM unit_of_measure WHERE name = 'TestUnitX'")
        self.conn.commit()
        self.conn.close()

    def test_settings_get_set(self):
        settings_repository.set_setting("TEST_CONFIG_PARAM", "HelloConfig")
        val = settings_repository.get_setting("TEST_CONFIG_PARAM")
        self.assertEqual(val, "HelloConfig")

    def test_number_series_increment(self):
        # Starts from current_number = 5, next should be 6
        # Format: TST-0006-OK (padding 4)
        formatted = settings_repository.increment_and_get_number("TEST_SERIES")
        self.assertEqual(formatted, "TST-0006-OK")
        
        # Next should be 7
        formatted2 = settings_repository.increment_and_get_number("TEST_SERIES")
        self.assertEqual(formatted2, "TST-0007-OK")

    def test_categories_crud(self):
        cat_id = settings_repository.add_category("TestCatX")
        categories = [c["name"] for c in settings_repository.get_all_categories()]
        self.assertIn("TestCatX", categories)
        
        settings_repository.update_category(cat_id, "TestCatX", is_active=0)
        row = [c for c in settings_repository.get_all_categories() if c["id"] == cat_id][0]
        self.assertEqual(row["is_active"], 0)
        
        settings_repository.delete_category(cat_id)
        categories_after = [c["name"] for c in settings_repository.get_all_categories()]
        self.assertNotIn("TestCatX", categories_after)

    def test_units_crud(self):
        unit_id = settings_repository.add_unit("TestUnitX")
        units = [u["name"] for u in settings_repository.get_all_units()]
        self.assertIn("TestUnitX", units)
        
        settings_repository.delete_unit(unit_id)
        units_after = [u["name"] for u in settings_repository.get_all_units()]
        self.assertNotIn("TestUnitX", units_after)

if __name__ == "__main__":
    unittest.main()
