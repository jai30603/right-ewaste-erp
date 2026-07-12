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

    def test_purchase_totals_multi_item_differing_gst(self):
        # Intra-state check
        result = build_purchase_totals(
            [
                {"amount": 1000.0, "gst_percentage": 18},
                {"amount": 500.0, "gst_percentage": 5}
            ],
            "27",
            "27",
        )
        self.assertEqual(result["subtotal"], 1500.0)
        self.assertEqual(result["cgst"], 102.50)
        self.assertEqual(result["sgst"], 102.50)
        self.assertEqual(result["igst"], 0.0)
        self.assertEqual(result["grand_total"], 1705.0)

        # Inter-state check
        result_inter = build_purchase_totals(
            [
                {"amount": 1000.0, "gst_percentage": 18},
                {"amount": 500.0, "gst_percentage": 5}
            ],
            "27",
            "19",
        )
        self.assertEqual(result_inter["subtotal"], 1500.0)
        self.assertEqual(result_inter["cgst"], 0.0)
        self.assertEqual(result_inter["sgst"], 0.0)
        self.assertEqual(result_inter["igst"], 205.0)
        self.assertEqual(result_inter["grand_total"], 1705.0)

    def test_purchase_totals_rounding_and_round_off(self):
        result = build_purchase_totals(
            [{"amount": 10.25, "gst_percentage": 18}],
            "27",
            "19",
        )
        self.assertEqual(result["subtotal"], 10.25)
        self.assertEqual(result["igst"], 1.85) # 10.25 * 0.18 = 1.845, rounded to 1.85
        self.assertEqual(result["grand_total"], 12.0) # 10.25 + 1.85 = 12.10, rounded to 12.0
        self.assertEqual(result["round_off"], -0.10)

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
