import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "backend"))
sys.path.insert(0, str(BASE_DIR))

import unittest
from datetime import date, timedelta
from backend.routes.sales import get_filter_date_range

class DateRangeFilteringTest(unittest.TestCase):
    def test_preset_today(self):
        start, end = get_filter_date_range("today", "all", "all", "", "")
        today = date.today().isoformat()
        self.assertEqual(start, today)
        self.assertEqual(end, today)

    def test_preset_this_month(self):
        start, end = get_filter_date_range("this_month", "all", "all", "", "")
        today = date.today()
        first_day = today.replace(day=1).isoformat()
        self.assertEqual(start, first_day)
        self.assertEqual(end, today.isoformat())

    def test_specific_year_only(self):
        start, end = get_filter_date_range("all", "2025", "all", "", "")
        self.assertEqual(start, "2025-01-01")
        self.assertEqual(end, "2025-12-31")

    def test_specific_year_and_month(self):
        start, end = get_filter_date_range("all", "2025", "05", "", "")
        self.assertEqual(start, "2025-05-01")
        self.assertEqual(end, "2025-05-31")

    def test_custom_range(self):
        start, end = get_filter_date_range("custom", "all", "all", "2025-06-15", "2025-07-20")
        self.assertEqual(start, "2025-06-15")
        self.assertEqual(end, "2025-07-20")

if __name__ == "__main__":
    unittest.main()
