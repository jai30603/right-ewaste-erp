import unittest
from unittest.mock import patch

from backend.services.purchase_service import build_purchase_totals, generate_purchase_invoice_number


class PurchaseServiceTest(unittest.TestCase):
    def test_purchase_totals_use_shared_gst_logic(self):
        result = build_purchase_totals(
            [{"amount": 1000, "gst_percentage": 18}],
            "27",
            "27",
        )
        self.assertEqual(result["cgst"], 90.0)
        self.assertEqual(result["sgst"], 90.0)
        self.assertEqual(result["igst"], 0.0)
        self.assertEqual(result["grand_total"], 1180.0)

    def test_generate_purchase_invoice_number_uses_numeric_suffix(self):
        class FakeCursor:
            def execute(self, *args, **kwargs):
                return None

            def fetchall(self):
                return [["PINV-2026-00005"], ["PINV-2026-00003"]]

        class FakeConn:
            def cursor(self):
                return FakeCursor()

            def close(self):
                return None

        with patch("backend.services.purchase_service.get_connection", return_value=FakeConn()):
            self.assertEqual(generate_purchase_invoice_number(), "PINV-2026-00006")


if __name__ == "__main__":
    unittest.main()
