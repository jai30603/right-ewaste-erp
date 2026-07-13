import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "backend"))
sys.path.insert(0, str(BASE_DIR))

import unittest
from backend.services.inventory_service import calculate_running_balance


class InventoryServiceTest(unittest.TestCase):
    def test_running_balance_purchases_and_sales(self):
        # Mock ledger records
        records = [
            {"date": "2026-07-01", "ref_number": "PUR-01", "type": "Purchase", "qty": 100.0, "rate": 10.0},
            {"date": "2026-07-02", "ref_number": "SAL-01", "type": "Sale", "qty": 30.0, "rate": 15.0},
            {"date": "2026-07-03", "ref_number": "PUR-02", "type": "Purchase", "qty": 50.0, "rate": 12.0},
            {"date": "2026-07-04", "ref_number": "SAL-02", "type": "Sale", "qty": 80.0, "rate": 16.0},
        ]
        
        result = calculate_running_balance(records)
        
        # Assert running balance counts
        self.assertEqual(result[0]["balance"], 100.0)  # Purchase +100
        self.assertEqual(result[1]["balance"], 70.0)   # Sale -30
        self.assertEqual(result[2]["balance"], 120.0)  # Purchase +50
        self.assertEqual(result[3]["balance"], 40.0)   # Sale -80


if __name__ == "__main__":
    unittest.main()
