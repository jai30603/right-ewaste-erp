import sys
import unittest
from pathlib import Path
import sqlite3

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "backend"))
sys.path.insert(0, str(BASE_DIR))

from backend.repositories.purchase_repository import (
    get_all_purchase_invoices, get_purchase_register_rows,
    increment_purchase_print_count, increment_purchase_pdf_download_count,
    get_purchase_invoice_by_id
)

class PurchaseEnhancementsTest(unittest.TestCase):
    def test_increment_purchase_print_pdf_download_counters(self):
        # Find a valid purchase invoice ID from DB to test increments
        conn = sqlite3.connect("database/erp.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id, print_count, pdf_download_count FROM purchase_invoice LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        
        if row:
            inv_id, print_cnt_before, pdf_cnt_before = row
            
            # Increment
            increment_purchase_print_count(inv_id)
            increment_purchase_pdf_download_count(inv_id)
            
            # Check after
            updated = get_purchase_invoice_by_id(inv_id)
            self.assertEqual(updated["print_count"], print_cnt_before + 1)
            self.assertEqual(updated["pdf_download_count"], pdf_cnt_before + 1)

    def test_purchase_register_gst_split_intra_vs_inter(self):
        # Test tax split rules on register rows helper for purchase
        rows = get_purchase_register_rows()
        if rows:
            for r in rows:
                is_intra = (r["state"] == "Maharashtra") # Company code state is 27, Maharashtra
                if is_intra:
                    self.assertTrue(r["cgst"] >= 0)
                    self.assertTrue(r["sgst"] >= 0)
                    self.assertEqual(r["igst"], 0.0)
                else:
                    self.assertEqual(r["cgst"], 0.0)
                    self.assertEqual(r["sgst"], 0.0)
                    self.assertTrue(r["igst"] >= 0)
                self.assertAlmostEqual(r["gst_total"], r["cgst"] + r["sgst"] + r["igst"], places=2)

    def test_get_all_purchase_invoices_filters(self):
        # Test filters in get_all_purchase_invoices
        all_inv = get_all_purchase_invoices()
        intra_inv = get_all_purchase_invoices(gst_type="INTRA")
        inter_inv = get_all_purchase_invoices(gst_type="INTER")
        
        self.assertTrue(len(intra_inv) + len(inter_inv) <= len(all_inv))

    def test_purchase_invoice_number_six_digit_format(self):
        from backend.repositories.purchase_repository import _generate_purchase_invoice_number
        conn = sqlite3.connect("database/erp.db")
        cursor = conn.cursor()
        num = _generate_purchase_invoice_number(cursor)
        conn.close()
        
        import re
        # Format must match PUR-YYYY-XXXXXX (6 digits)
        self.assertTrue(re.match(r"^PUR-\d{4}-\d{6}$", num), f"Number '{num}' did not match PUR-YYYY-XXXXXX format")

    def test_purchase_intake_type_database_retrieval(self):
        from backend.repositories.purchase_repository import create_purchase_invoice, get_purchase_invoice_by_id
        conn = sqlite3.connect("database/erp.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id, state_code FROM party WHERE is_active = 1 LIMIT 1")
        party_row = cursor.fetchone()
        conn.close()
        
        if party_row:
            party_id, party_state = party_row
            items = [{"material_id": 1, "qty": 10.0, "weight": 5.0, "rate": 100.0, "amount": 1000.0, "gst_percentage": 18.0}]
            
            invoice_id = create_purchase_invoice(
                party_id=party_id,
                invoice_date="2026-07-13",
                supplier_invoice_number="TEST-123",
                payment_mode="Cash",
                transporter="Self",
                vehicle_number="MH12AB1234",
                remarks="Test Intake Type",
                items=items,
                company_state_code="27",
                party_state_code=party_state,
                status="DRAFT",
                intake_type="Donation"
            )
            
            # Fetch and verify
            fetched = get_purchase_invoice_by_id(invoice_id)
            self.assertEqual(fetched["intake_type"], "Donation")

    def test_purchase_service_item_validations(self):
        from backend.services.purchase_service import validate_purchase_items
        
        # We need mock or dummy database material rows, but we can verify against existing DB materials:
        conn = sqlite3.connect("database/erp.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id, tracking_type FROM material WHERE is_active = 1 LIMIT 3")
        materials = cursor.fetchall()
        conn.close()
        
        for mid, tracking in materials:
            errors = {}
            if tracking == "WEIGHT_ONLY":
                # Missing weight should trigger error
                items = [{"material_id": mid, "qty": 1.0, "weight": 0.0, "rate": 50.0, "amount": 50.0}]
                validate_purchase_items(items, errors)
                self.assertTrue(any("Weight is required" in msg for msg in errors.values()))
            elif tracking == "QUANTITY_ONLY":
                # Missing quantity should trigger error.
                items = [{"material_id": mid, "qty": 0.0, "weight": 5.0, "rate": 50.0, "amount": 50.0}]
                validate_purchase_items(items, errors)
                self.assertTrue(any("Quantity is required" in msg for msg in errors.values()))
            elif tracking == "BOTH":
                # Missing either should trigger error
                items = [{"material_id": mid, "qty": 1.0, "weight": 0.0, "rate": 50.0, "amount": 50.0}]
                validate_purchase_items(items, errors)
                self.assertTrue(any("Weight is required" in msg for msg in errors.values()))



if __name__ == "__main__":
    unittest.main()
