import unittest

from backend.services.invoice_service import calculate_gst


class InvoiceServiceTest(unittest.TestCase):
    def test_intra_state_gst_is_split_between_cgst_and_sgst(self):
        result = calculate_gst(
            1000,
            [{"amount": 1000, "gst_percentage": 18}],
            "27",
            "27",
        )
        self.assertEqual(result["cgst"], 90.0)
        self.assertEqual(result["sgst"], 90.0)
        self.assertEqual(result["igst"], 0.0)
        self.assertEqual(result["grand_total"], 1180.0)

    def test_legacy_signature_is_supported(self):
        result = calculate_gst("27", "27", 1000, 18)
        self.assertEqual(result["cgst"], 90.0)
        self.assertEqual(result["sgst"], 90.0)
        self.assertEqual(result["igst"], 0.0)
        self.assertEqual(result["grand_total"], 1180.0)


if __name__ == "__main__":
    unittest.main()
