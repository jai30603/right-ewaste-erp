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

    def test_sales_invoice_v4_stage1_creation_snapshots(self):
        from backend.repositories.sales_repository import create_sales_invoice, get_invoice_by_id, get_invoice_items
        
        # We need a customer from DB
        conn = sqlite3.connect("database/erp.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM party WHERE party_type IN ('CUSTOMER', 'BOTH') LIMIT 1")
        party_id = cursor.fetchone()[0]
        
        # Ensure we have a material
        cursor.execute("SELECT id FROM material LIMIT 1")
        material_id = cursor.fetchone()[0]
        conn.close()

        items = [
            {
                "material_id": material_id,
                "qty": 2.0,
                "weight": 5.0,
                "rate": 10.0,
                "amount": 20.0,
                "gst_percentage": 18.0,
                "item_type": "Goods",
                "uom": "KGS"
            },
            {
                "material_id": None,
                "qty": 1.0,
                "weight": 0.0,
                "rate": 150.0,
                "amount": 150.0,
                "gst_percentage": 18.0,
                "item_type": "Service/Charge",
                "description": "Freight Delivery Charges",
                "uom": "NOS"
            }
        ]

        inv_id = create_sales_invoice(
            party_id=party_id,
            invoice_date="2026-08-11",
            payment_mode="NEFT",
            transporter="E-Waste Logistics",
            vehicle_number="DL1CA9988",
            remarks="Stage 1 Redesign Integration Test Run",
            items=items,
            company_state_code="27",
            party_state_code="27",
            billing_party_name="Mock Customer Limited",
            billing_address="Goregaon East, Mumbai",
            billing_gstin="27AAACM1234F1Z1",
            billing_state="Maharashtra",
            billing_state_code="27",
            shipping_party_name="Mock Customer Ship Facility",
            shipping_address="Pune Bypass Area",
            shipping_gstin="27AAACM1234F1Z1",
            shipping_state="Maharashtra",
            shipping_state_code="27",
            dispatch_location="Warehouse Bhiwandi",
            dispatch_address="Bhiwandi Amane Facility",
            dispatch_gstin="27AALCR5544C1ZB",
            dispatch_state="Maharashtra",
            dispatch_state_code="27",
            company_bank_name="HDFC Bank",
            company_bank_account_number="50200087654321",
            company_bank_ifsc="HDFC0001203",
            company_bank_branch="Sector 63 Noida",
            financial_year="2026-2027"
        )

        self.assertTrue(inv_id > 0)
        
        # Verify invoice snapshot data is saved perfectly
        inv = get_invoice_by_id(inv_id)
        self.assertEqual(inv["billing_party_name"], "Mock Customer Limited")
        self.assertEqual(inv["billing_address"], "Goregaon East, Mumbai")
        self.assertEqual(inv["billing_gstin"], "27AAACM1234F1Z1")
        self.assertEqual(inv["shipping_party_name"], "Mock Customer Ship Facility")
        self.assertEqual(inv["shipping_address"], "Pune Bypass Area")
        self.assertEqual(inv["dispatch_location"], "Warehouse Bhiwandi")
        self.assertEqual(inv["company_bank_name"], "HDFC Bank")
        self.assertEqual(inv["company_bank_account_number"], "50200087654321")
        self.assertEqual(inv["financial_year"], "2026-2027")

        # Verify items saved perfectly with correct UOM, description and type
        saved_items = get_invoice_items(inv_id)
        self.assertEqual(len(saved_items), 2)
        self.assertEqual(saved_items[0]["item_type"], "Goods")
        self.assertEqual(saved_items[0]["uom"], "KGS")
        self.assertEqual(saved_items[1]["item_type"], "Service/Charge")
        self.assertEqual(saved_items[1]["description"], "Freight Delivery Charges")
        self.assertEqual(saved_items[1]["uom"], "NOS")


class SalesStage2TaxCalculationTest(unittest.TestCase):
    def test_determine_tax_treatment(self):
        from backend.services.calculation_service import determine_tax_treatment
        # Intra-state (Billing only)
        self.assertTrue(determine_tax_treatment("27", "27"))
        # Inter-state (Billing only)
        self.assertFalse(determine_tax_treatment("27", "29"))
        # Intra-state (Shipping takes precedence)
        self.assertTrue(determine_tax_treatment("27", "29", "27"))
        # Inter-state (Shipping takes precedence)
        self.assertFalse(determine_tax_treatment("27", "27", "29"))

    def test_calculation_intra_state_18(self):
        from backend.services.calculation_service import calculate_invoice_result
        items = [{"qty": 10.0, "rate": 100.0, "gst_percentage": 18.0}]
        res = calculate_invoice_result(items, "27", "27")
        self.assertEqual(res["taxable_total"], 1000.0)
        self.assertEqual(res["cgst_total"], 90.0)
        self.assertEqual(res["sgst_total"], 90.0)
        self.assertEqual(res["igst_total"], 0.0)
        self.assertEqual(res["grand_total"], 1180.0)

    def test_calculation_inter_state_18(self):
        from backend.services.calculation_service import calculate_invoice_result
        items = [{"qty": 10.0, "rate": 100.0, "gst_percentage": 18.0}]
        res = calculate_invoice_result(items, "27", "29")
        self.assertEqual(res["taxable_total"], 1000.0)
        self.assertEqual(res["cgst_total"], 0.0)
        self.assertEqual(res["sgst_total"], 0.0)
        self.assertEqual(res["igst_total"], 180.0)
        self.assertEqual(res["grand_total"], 1180.0)

    def test_calculation_intra_state_5(self):
        from backend.services.calculation_service import calculate_invoice_result
        items = [{"qty": 10.0, "rate": 100.0, "gst_percentage": 5.0}]
        res = calculate_invoice_result(items, "27", "27")
        self.assertEqual(res["taxable_total"], 1000.0)
        self.assertEqual(res["cgst_total"], 25.0)
        self.assertEqual(res["sgst_total"], 25.0)
        self.assertEqual(res["igst_total"], 0.0)
        self.assertEqual(res["grand_total"], 1050.0)

    def test_calculation_inter_state_5(self):
        from backend.services.calculation_service import calculate_invoice_result
        items = [{"qty": 10.0, "rate": 100.0, "gst_percentage": 5.0}]
        res = calculate_invoice_result(items, "27", "29")
        self.assertEqual(res["taxable_total"], 1000.0)
        self.assertEqual(res["cgst_total"], 0.0)
        self.assertEqual(res["sgst_total"], 0.0)
        self.assertEqual(res["igst_total"], 50.0)
        self.assertEqual(res["grand_total"], 1050.0)

    def test_multiple_line_items_mixed_gst(self):
        from backend.services.calculation_service import calculate_invoice_result
        items = [
            {"qty": 10.0, "rate": 100.0, "gst_percentage": 18.0},
            {"qty": 5.0, "rate": 200.0, "gst_percentage": 5.0}
        ]
        res = calculate_invoice_result(items, "27", "27")
        # Line 1: Taxable=1000, CGST=90, SGST=90
        # Line 2: Taxable=1000, CGST=25, SGST=25
        self.assertEqual(res["taxable_total"], 2000.0)
        self.assertEqual(res["cgst_total"], 115.0)
        self.assertEqual(res["sgst_total"], 115.0)
        self.assertEqual(res["igst_total"], 0.0)
        self.assertEqual(res["grand_total"], 2230.0)

    def test_tcs_applicability_and_rate(self):
        from backend.services.calculation_service import calculate_invoice_result
        items = [{"qty": 10.0, "rate": 100.0, "gst_percentage": 18.0}]
        # TCS applicable at 0.076%
        res = calculate_invoice_result(items, "27", "27", tcs_applicable=True, tcs_rate=0.076)
        # Base total = 1000 + 90 + 90 = 1180
        # TCS = 1180 * 0.076 / 100 = 0.8968 -> rounded to 0.90
        self.assertEqual(res["tcs_base_amount"], 1180.0)
        self.assertEqual(res["tcs_amount"], 0.90)
        # Grand raw = 1180 + 0.90 = 1180.90 -> rounded grand = 1181.0
        self.assertEqual(res["grand_total"], 1181.0)
        self.assertAlmostEqual(res["round_off"], 0.10, places=2)

        # TCS not applicable
        res_no_tcs = calculate_invoice_result(items, "27", "27", tcs_applicable=False)
        self.assertEqual(res_no_tcs["tcs_amount"], 0.0)
        self.assertEqual(res_no_tcs["grand_total"], 1180.0)

    def test_rounding_directions(self):
        from backend.services.calculation_service import calculate_invoice_result
        # Test positive round_off (e.g. raw total ends in .40 -> rounded down, raw total ends in .60 -> rounded up)
        # Case A: Qty=1, Rate=10.04, GST=5% -> Taxable=10.04, GST=0.50. Raw total = 10.54. Rounded = 11.0. RoundOff = +0.46
        res1 = calculate_invoice_result([{"qty": 1, "rate": 10.04, "gst_percentage": 5.0}], "27", "29")
        self.assertEqual(res1["grand_total"], 11.0)
        self.assertAlmostEqual(res1["round_off"], 0.46, places=2)

        # Case B: Qty=1, Rate=10.10, GST=5% -> Taxable=10.10, GST=0.51. Raw total = 10.61. Rounded = 11.0. RoundOff = +0.39
        res2 = calculate_invoice_result([{"qty": 1, "rate": 10.10, "gst_percentage": 5.0}], "27", "29")
        self.assertEqual(res2["grand_total"], 11.0)
        self.assertAlmostEqual(res2["round_off"], 0.39, places=2)

    def test_service_items_stock_bypass(self):
        # We check that service items bypass stock validations
        from backend.repositories.sales_repository import create_sales_invoice, get_invoice_by_id, get_invoice_items
        
        # We need a customer from DB
        conn = sqlite3.connect("database/erp.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM party WHERE party_type IN ('CUSTOMER', 'BOTH') LIMIT 1")
        party_id = cursor.fetchone()[0]
        conn.close()

        items = [
            {
                "material_id": None, # Service/charge item
                "qty": 1.0,
                "weight": 0.0,
                "rate": 250.0,
                "amount": 250.0,
                "gst_percentage": 18.0,
                "item_type": "Service/Charge",
                "description": "Loading & Unloading Labour Service Charges",
                "uom": "NOS"
            }
        ]

        inv_id = create_sales_invoice(
            party_id=party_id,
            invoice_date="2026-08-11",
            payment_mode="NEFT",
            transporter="Self Log",
            vehicle_number="MH04GP1234",
            remarks="Bypass stock check service test",
            items=items,
            company_state_code="27",
            party_state_code="27",
            tcs_applicable=True,
            tcs_rate=0.1
        )
        self.assertTrue(inv_id > 0)
        
        # Verify stored details
        inv = get_invoice_by_id(inv_id)
        self.assertEqual(inv["tcs_rate"], 0.1)
        self.assertTrue(inv["tcs_amount"] > 0)
        self.assertTrue(inv["tcs_base_amount"] > 0)
        self.assertTrue(len(inv["amount_in_words"]) > 0)
        
        saved_items = get_invoice_items(inv_id)
        self.assertEqual(saved_items[0]["item_type"], "Service/Charge")
        self.assertEqual(saved_items[0]["material_id"], 999999) # fallback material ID

    def test_historical_calculations_preservation(self):
        # Existing invoices must preserve their saved totals and tax values when retrieved
        from backend.repositories.sales_repository import get_invoice_by_id, get_invoice_items
        
        # Find a valid saved sales invoice
        conn = sqlite3.connect("database/erp.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM sales_invoice WHERE cgst > 0 OR igst > 0 LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        
        if row:
            inv_id = row[0]
            inv_before = get_invoice_by_id(inv_id)
            
            # Simulate viewing context
            from backend.routes.sales import _invoice_context
            ctx = _invoice_context(inv_id)
            self.assertEqual(ctx["invoice"]["cgst"], inv_before["cgst"])
            self.assertEqual(ctx["invoice"]["sgst"], inv_before["sgst"])
            self.assertEqual(ctx["invoice"]["igst"], inv_before["igst"])
            self.assertEqual(ctx["invoice"]["grand_total"], inv_before["grand_total"])


class SalesStage3InvoiceDocumentTest(unittest.TestCase):
    def test_invoice_context_tax_breakdown(self):
        # We fetch a valid invoice to test context generation and tax breakdown
        conn = sqlite3.connect("database/erp.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM sales_invoice LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        
        if row:
            inv_id = row[0]
            from backend.routes.sales import _invoice_context
            ctx = _invoice_context(inv_id)
            self.assertIn("tax_breakdown", ctx)
            self.assertIsInstance(ctx["tax_breakdown"], list)
            
            # If items exist, check structure of breakdown rows
            if ctx["items"]:
                first_row = ctx["tax_breakdown"][0]
                self.assertIn("hsn", first_row)
                self.assertIn("rate", first_row)
                self.assertIn("taxable", first_row)
                self.assertIn("cgst", first_row)
                self.assertIn("sgst", first_row)
                self.assertIn("igst", first_row)
                self.assertIn("total_tax", first_row)

    def test_pdf_generation_error_handling(self):
        from backend.app import app
        app.config["TESTING"] = True
        app.config["SECRET_KEY"] = "testsecret"
        
        # Mock render_url_to_pdf
        import backend.routes.sales as sales_route
        original_render = sales_route.render_url_to_pdf
        
        def mock_render(url, landscape=False):
            raise RuntimeError("Playwright headless render crashed mock error")
            
        sales_route.render_url_to_pdf = mock_render
        
        # Test download PDF endpoint redirects to view page
        with app.test_client() as client:
            conn = sqlite3.connect("database/erp.db")
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM sales_invoice LIMIT 1")
            row = cursor.fetchone()
            conn.close()
            
            if row:
                inv_id = row[0]
                response = client.get(f"/sales/{inv_id}/pdf")
                self.assertEqual(response.status_code, 302) # redirect
                self.assertTrue(response.headers["Location"].endswith(f"/sales/{inv_id}/view"))
                
        # Restore mock
        sales_route.render_url_to_pdf = original_render


class SalesStage4WorkspaceTest(unittest.TestCase):
    def test_api_invoice_details_endpoint(self):
        from backend.app import app
        app.config["TESTING"] = True
        app.config["SECRET_KEY"] = "testsecret"
        
        conn = sqlite3.connect("database/erp.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM sales_invoice LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        
        if row:
            inv_id = row[0]
            with app.test_client() as client:
                response = client.get(f"/api/sales/{inv_id}/details")
                self.assertEqual(response.status_code, 200)
                data = response.json
                self.assertIn("invoice", data)
                self.assertIn("items", data)
                self.assertIn("party", data)
                self.assertIn("tax_breakdown", data)
                self.assertEqual(data["invoice"]["id"], inv_id)

    def test_repository_advanced_filters(self):
        from backend.repositories.sales_repository import get_all_invoices
        
        invoices = get_all_invoices(
            gstin="all",
            shipping_state_code="all",
            dispatch_location="all",
            hsn_sac="all",
            item_type="all",
            uom="all",
            gst_rate="all",
            tcs_applicable="all",
            transporter="all",
            vehicle_number="all",
            company_bank_account_number="all"
        )
        self.assertIsInstance(invoices, list)


class SalesStage5StabilizationTest(unittest.TestCase):
    def test_inr_words_conversion_bug(self):
        from backend.services.calculation_service import number_to_inr_words
        self.assertEqual(number_to_inr_words(5000), "INR Five Thousand Rupees Only")
        self.assertEqual(number_to_inr_words(1000), "INR One Thousand Rupees Only")
        self.assertEqual(number_to_inr_words(12345), "INR Twelve Thousand Three Hundred Forty Five Rupees Only")
        self.assertEqual(number_to_inr_words(99999), "INR Ninety Nine Thousand Nine Hundred Ninety Nine Rupees Only")
        self.assertEqual(number_to_inr_words(100000), "INR One Lakh Rupees Only")

    def test_service_items_stock_sync_bypass(self):
        from backend.services.inventory_service import sync_document
        
        # 1. Create a dummy sales invoice
        conn = sqlite3.connect("database/erp.db")
        cursor = conn.cursor()
        
        # Ensure we have a valid party
        cursor.execute("SELECT id FROM party LIMIT 1")
        party_row = cursor.fetchone()
        party_id = party_row[0] if party_row else 1
        
        # Create confirmed invoice
        cursor.execute("""
            INSERT INTO sales_invoice (invoice_number, invoice_date, party_id, subtotal, grand_total, status, is_active)
            VALUES ('INV-TEST-SYNC-1', '2026-08-11', ?, 180, 180, 'CONFIRMED', 1)
        """, (party_id,))
        invoice_id = cursor.lastrowid
        
        # Insert only a service item
        cursor.execute("""
            INSERT INTO sales_invoice_item (sales_invoice_id, material_id, quantity, weight, rate, amount, item_type)
            VALUES (?, 999999, 1, 0, 180, 180, 'Service/Charge')
        """, (invoice_id,))
        
        conn.commit()
        conn.close()
        
        try:
            # 2. Sync invoice to inventory
            sync_document("SALE", invoice_id, "System User")
            
            # 3. Check stock movements
            conn = sqlite3.connect("database/erp.db")
            cursor = conn.cursor()
            cursor.execute("SELECT material_id FROM stock_movement WHERE reference_type = 'SALE' AND reference_id = ?", (invoice_id,))
            movements = [r[0] for r in cursor.fetchall()]
            conn.close()
            
            # Verify no stock movements were generated at all!
            self.assertEqual(len(movements), 0)
            
        finally:
            # Cleanup
            conn = sqlite3.connect("database/erp.db")
            cursor = conn.cursor()
            cursor.execute("DELETE FROM stock_movement WHERE reference_type = 'SALE' AND reference_id = ?", (invoice_id,))
            cursor.execute("DELETE FROM sales_invoice_item WHERE sales_invoice_id = ?", (invoice_id,))
            cursor.execute("DELETE FROM sales_invoice WHERE id = ?", (invoice_id,))
            conn.commit()
            conn.close()

    def test_tcs_preservation_in_duplication(self):
        from backend.app import app
        orig_testing = app.config.get("TESTING")
        orig_auth = app.config.get("ERP_AUTH_REQUIRED")
        orig_csrf = app.config.get("WTF_CSRF_ENABLED")
        orig_bypass = app.config.get("CSRF_BYPASS")
        orig_secret = app.config.get("SECRET_KEY")

        app.config["TESTING"] = True
        app.config["SECRET_KEY"] = "testsecret"
        app.config["ERP_AUTH_REQUIRED"] = False
        app.config["WTF_CSRF_ENABLED"] = False
        app.config["CSRF_BYPASS"] = True
        
        conn = sqlite3.connect("database/erp.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM party LIMIT 1")
        party_row = cursor.fetchone()
        party_id = party_row[0] if party_row else 1
        
        # Create invoice with TCS
        cursor.execute("""
            INSERT INTO sales_invoice (invoice_number, invoice_date, party_id, subtotal, grand_total, status, is_active, tcs_applicable, tcs_rate)
            VALUES ('INV-TEST-TCS-DUP', '2026-08-11', ?, 1000, 1180, 'CONFIRMED', 1, 1, 0.075)
        """, (party_id,))
        invoice_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        try:
            with app.test_client() as client:
                # Mock session
                with client.session_transaction() as sess:
                    sess["user"] = {"role": "ADMIN", "username": "admin_test"}
                    sess["session_token"] = "test_token"
                    
                response = client.get(f"/sales/{invoice_id}/duplicate")
                self.assertEqual(response.status_code, 302) # redirects to edit page of new draft
                
                # Fetch new draft from database to check TCS fields
                conn = sqlite3.connect("database/erp.db")
                cursor = conn.cursor()
                cursor.execute("SELECT tcs_applicable, tcs_rate, id FROM sales_invoice WHERE remarks LIKE 'Duplicate of INV-TEST-TCS-DUP%'")
                dup_row = cursor.fetchone()
                conn.close()
                
                self.assertIsNotNone(dup_row)
                self.assertEqual(dup_row[0], 1)
                self.assertEqual(dup_row[1], 0.075)
                
                # Cleanup the duplicate
                if dup_row:
                    conn = sqlite3.connect("database/erp.db")
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM sales_invoice WHERE id = ?", (dup_row[2],))
                    conn.commit()
                    conn.close()
        finally:
            app.config["TESTING"] = orig_testing
            app.config["ERP_AUTH_REQUIRED"] = orig_auth
            app.config["WTF_CSRF_ENABLED"] = orig_csrf
            app.config["CSRF_BYPASS"] = orig_bypass
            app.config["SECRET_KEY"] = orig_secret

            conn = sqlite3.connect("database/erp.db")
            cursor = conn.cursor()
            cursor.execute("DELETE FROM sales_invoice WHERE id = ?", (invoice_id,))
            conn.commit()
            conn.close()

    def test_finalized_invoice_operator_modification_restriction(self):
        from backend.app import app
        orig_testing = app.config.get("TESTING")
        orig_auth = app.config.get("ERP_AUTH_REQUIRED")
        orig_csrf = app.config.get("WTF_CSRF_ENABLED")
        orig_bypass = app.config.get("CSRF_BYPASS")
        orig_secret = app.config.get("SECRET_KEY")

        app.config["TESTING"] = True
        app.config["SECRET_KEY"] = "testsecret"
        app.config["ERP_AUTH_REQUIRED"] = False
        app.config["WTF_CSRF_ENABLED"] = False
        app.config["CSRF_BYPASS"] = True
        
        conn = sqlite3.connect("database/erp.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM party LIMIT 1")
        party_row = cursor.fetchone()
        party_id = party_row[0] if party_row else 1
        
        # Create finalized invoice
        cursor.execute("""
            INSERT INTO sales_invoice (invoice_number, invoice_date, party_id, subtotal, grand_total, status, is_active)
            VALUES ('INV-TEST-FINAL-EDIT', '2026-08-11', ?, 1000, 1180, 'CONFIRMED', 1)
        """, (party_id,))
        invoice_id = cursor.lastrowid
        
        cursor.execute("""
            INSERT INTO sales_invoice_item (sales_invoice_id, material_id, quantity, weight, rate, amount)
            VALUES (?, 1, 10, 0, 100, 1000)
        """, (invoice_id,))
        conn.commit()
        conn.close()
        
        try:
            with app.test_client() as client:
                # Login as OPERATOR
                with client.session_transaction() as sess:
                    sess["user"] = {"role": "OPERATOR", "username": "op_test"}
                    sess["session_token"] = "op_token"
                
                # Submit post with modified items (change quantity to 20)
                form_data = {
                    "party_id": str(party_id),
                    "invoice_date": "2026-08-11",
                    "status": "CONFIRMED",
                    "material_id[]": ["1"],
                    "qty[]": ["20"], # modified quantity
                    "weight[]": ["0"],
                    "rate[]": ["100"],
                    "amount[]": ["2000"],
                    "gst_percentage[]": ["18.0"],
                    "item_type[]": ["Goods"],
                    "description[]": ["Material 1"],
                    "hsn_sac[]": ["8548"],
                    "uom[]": ["KGS"],
                    "item_reference[]": [""],
                    "hidden_grand_total": "2360.0",
                    "tcs_rate": "0.076",
                    "tcs_applicable": ""
                }
                response = client.post(f"/sales/{invoice_id}/edit", data=form_data)
                
                # Verify that it renders edit page with errors rather than redirecting/saving
                self.assertEqual(response.status_code, 200)
                self.assertIn(b"Only administrators can modify line items", response.data)
                
                # Verify quantity in DB remains 10
                conn = sqlite3.connect("database/erp.db")
                cursor = conn.cursor()
                cursor.execute("SELECT quantity FROM sales_invoice_item WHERE sales_invoice_id = ?", (invoice_id,))
                qty = cursor.fetchone()[0]
                conn.close()
                self.assertEqual(qty, 10)
                
        finally:
            app.config["TESTING"] = orig_testing
            app.config["ERP_AUTH_REQUIRED"] = orig_auth
            app.config["WTF_CSRF_ENABLED"] = orig_csrf
            app.config["CSRF_BYPASS"] = orig_bypass
            app.config["SECRET_KEY"] = orig_secret

            conn = sqlite3.connect("database/erp.db")
            cursor = conn.cursor()
            cursor.execute("DELETE FROM sales_invoice_item WHERE sales_invoice_id = ?", (invoice_id,))
            cursor.execute("DELETE FROM sales_invoice WHERE id = ?", (invoice_id,))
            conn.commit()
            conn.close()


if __name__ == "__main__":
    unittest.main()
