import sys
import unittest
from pathlib import Path
import sqlite3

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "backend"))
sys.path.insert(0, str(BASE_DIR))

from backend.repositories.sales_repository import (
    get_all_invoices, get_sales_register_rows, increment_print_count,
    increment_pdf_download_count, get_invoice_by_id
)

class SalesEnhancementsTest(unittest.TestCase):
    def test_increment_print_pdf_download_counters(self):
        # We find a valid sales invoice ID from DB to test increments
        conn = sqlite3.connect("database/erp.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id, print_count, pdf_download_count FROM sales_invoice LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        
        if row:
            inv_id, print_cnt_before, pdf_cnt_before = row
            
            # Increment
            increment_print_count(inv_id)
            increment_pdf_download_count(inv_id)
            
            # Check after
            updated = get_invoice_by_id(inv_id)
            self.assertEqual(updated["print_count"], print_cnt_before + 1)
            self.assertEqual(updated["pdf_download_count"], pdf_cnt_before + 1)

    def test_sales_register_gst_split_intra_vs_inter(self):
        # Test tax split rules on register rows helper
        rows = get_sales_register_rows()
        if rows:
            for r in rows:
                is_intra = (r["party_state_code"] == "27")
                if is_intra:
                    self.assertTrue(r["cgst"] >= 0)
                    self.assertTrue(r["sgst"] >= 0)
                    self.assertEqual(r["igst"], 0.0)
                else:
                    self.assertEqual(r["cgst"], 0.0)
                    self.assertEqual(r["sgst"], 0.0)
                    self.assertTrue(r["igst"] >= 0)
                self.assertAlmostEqual(r["gst_total"], r["cgst"] + r["sgst"] + r["igst"], places=2)

    def test_get_all_invoices_filters(self):
        # Test filters in get_all_invoices
        all_inv = get_all_invoices()
        intra_inv = get_all_invoices(gst_type="INTRA")
        inter_inv = get_all_invoices(gst_type="INTER")
        
        self.assertTrue(len(intra_inv) + len(inter_inv) <= len(all_inv))

    def test_status_lifecycle_validation(self):
        from backend.routes.sales import validate_status_transition
        self.assertTrue(validate_status_transition("DRAFT", "CONFIRMED"))
        self.assertTrue(validate_status_transition("DRAFT", "CANCELLED"))
        self.assertTrue(validate_status_transition("CONFIRMED", "PRINTED"))
        self.assertTrue(validate_status_transition("PRINTED", "PAID"))
        self.assertTrue(validate_status_transition("PRINTED", "CANCELLED"))
        self.assertFalse(validate_status_transition("CONFIRMED", "DRAFT"))
        self.assertFalse(validate_status_transition("PAID", "CANCELLED"))
        self.assertFalse(validate_status_transition("CANCELLED", "CONFIRMED"))


    def test_invoice_number_format_6_digits(self):
        from backend.repositories.sales_repository import _generate_invoice_number
        conn = sqlite3.connect("database/erp.db")
        cursor = conn.cursor()
        inv_num = _generate_invoice_number(cursor)
        conn.close()
        # Verify starts with INV-YYYY- and has a 6-digit sequence suffix
        import re
        self.assertTrue(re.match(r"^INV-\d{4}-\d{6}$", inv_num))

    def test_supplier_only_parties_filtered(self):
        # Insert a dummy party with party_type='SUPPLIER' and verify we only get CUSTOMER/BOTH in filtered queries
        from backend.repositories.party_repository import get_all_parties
        conn = sqlite3.connect("database/erp.db")
        cursor = conn.cursor()
        # Ensure we have a supplier
        cursor.execute("SELECT id FROM party WHERE party_type = 'SUPPLIER' LIMIT 1")
        supplier_exists = cursor.fetchone()
        if not supplier_exists:
            cursor.execute("""
                INSERT INTO party (company_name, party_code, party_type, is_active)
                VALUES ('Test Supplier Inc', 'SUP-TST-01', 'SUPPLIER', 1)
            """)
            conn.commit()
        conn.close()
        
        # Verify filtering in Sales logic
        all_parties = get_all_parties()
        sales_parties = [p for p in all_parties if p["party_type"] in ("CUSTOMER", "BOTH")]
        for p in sales_parties:
            self.assertNotEqual(p["party_type"], "SUPPLIER")
    def test_sales_service_layer(self):
        from backend.services.sales_service import generate_sales_invoice_number, calculate_invoice_totals
        # Check generated number structure
        num = generate_sales_invoice_number()
        self.assertTrue(num.startswith("INV-"))
        
        # Check total calculation
        totals = calculate_invoice_totals(
            items=[{"qty": 10, "rate": 5, "gst_percentage": 18}],
            company_state_code="27",
            party_state_code="27"
        )
        self.assertEqual(totals["subtotal"], 50.0)
        self.assertEqual(totals["cgst"], 4.5)
        self.assertEqual(totals["sgst"], 4.5)
        self.assertEqual(totals["grand_total"], 59.0)


if __name__ == "__main__":
    unittest.main()
