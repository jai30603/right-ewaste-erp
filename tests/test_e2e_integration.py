import sys
import unittest
import sqlite3
import os
from pathlib import Path
from datetime import date

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "backend"))
sys.path.insert(0, str(BASE_DIR))

from database import get_connection
from repositories.purchase_repository import create_purchase_invoice
from repositories.sales_repository import create_sales_invoice
from services.inventory_service import sync_document
from services import processing_service, certificate_service
from repositories import inventory_repository, party_repository, certificate_repository
from repositories.dashboard_repository import get_dashboard_snapshot
from repositories.activity_log_repository import get_recent_activities
from app import app


class E2EIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config["TESTING"] = True
        self.app_context = self.app.test_request_context()
        self.app_context.push()

        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys = OFF")
            # Direct cleanup of child records referencing the test party to prevent foreign key errors
            cursor.execute("DELETE FROM sales_invoice_item WHERE sales_invoice_id IN (SELECT id FROM sales_invoice WHERE party_id IN (SELECT id FROM party WHERE party_code = 'TST_E2E_PRT'))")
            cursor.execute("DELETE FROM purchase_invoice_item WHERE purchase_invoice_id IN (SELECT id FROM purchase_invoice WHERE supplier_id IN (SELECT id FROM party WHERE party_code = 'TST_E2E_PRT'))")
            cursor.execute("DELETE FROM sales_invoice WHERE party_id IN (SELECT id FROM party WHERE party_code = 'TST_E2E_PRT')")
            cursor.execute("DELETE FROM purchase_invoice WHERE supplier_id IN (SELECT id FROM party WHERE party_code = 'TST_E2E_PRT')")

            # Clean up leftovers in correct order targeting test materials directly to resolve foreign keys
            cursor.execute("DELETE FROM sales_invoice_item WHERE material_id IN (SELECT id FROM material WHERE material_code IN ('TST_E2E_RAW', 'TST_E2E_REC'))")
            cursor.execute("DELETE FROM purchase_invoice_item WHERE material_id IN (SELECT id FROM material WHERE material_code IN ('TST_E2E_RAW', 'TST_E2E_REC'))")
            cursor.execute("DELETE FROM processing_input WHERE material_id IN (SELECT id FROM material WHERE material_code IN ('TST_E2E_RAW', 'TST_E2E_REC'))")
            cursor.execute("DELETE FROM processing_output WHERE material_id IN (SELECT id FROM material WHERE material_code IN ('TST_E2E_RAW', 'TST_E2E_REC')) OR recovered_from_material_id IN (SELECT id FROM material WHERE material_code IN ('TST_E2E_RAW', 'TST_E2E_REC'))")
            cursor.execute("DELETE FROM processing_loss WHERE processing_job_id IN (SELECT id FROM processing_job WHERE processing_number = 'PJ-E2E-01')")
            cursor.execute("DELETE FROM processing_job WHERE processing_number = 'PJ-E2E-01'")
            cursor.execute("DELETE FROM sales_invoice WHERE remarks LIKE '%E2E-TEST%'")
            cursor.execute("CREATE TEMP TABLE IF NOT EXISTS e2e_certificate_ids (id INTEGER PRIMARY KEY)")
            cursor.execute("DELETE FROM e2e_certificate_ids")
            cursor.execute("INSERT INTO e2e_certificate_ids SELECT id FROM certificate WHERE remarks LIKE '%E2E-TEST%'")
            cursor.execute("""INSERT OR IGNORE INTO e2e_certificate_ids
                              SELECT id FROM certificate
                              WHERE replaces_certificate_id IN (SELECT id FROM e2e_certificate_ids)
                                 OR superseded_certificate_id IN (SELECT id FROM e2e_certificate_ids)""")
            cursor.execute("DELETE FROM certificate_pdf WHERE certificate_id IN (SELECT id FROM e2e_certificate_ids)")
            cursor.execute("DELETE FROM certificate_activity WHERE certificate_id IN (SELECT id FROM e2e_certificate_ids)")
            cursor.execute("DELETE FROM certificate_asset_attachment WHERE certificate_id IN (SELECT id FROM e2e_certificate_ids)")
            cursor.execute("DELETE FROM certificate_processing WHERE processing_job_id IN (SELECT id FROM processing_job WHERE processing_number = 'PJ-E2E-01')")
            cursor.execute("DELETE FROM certificate_purchase WHERE purchase_id IN (SELECT id FROM purchase_invoice WHERE remarks LIKE '%E2E-TEST%')")
            cursor.execute("DELETE FROM certificate_processing WHERE certificate_id IN (SELECT id FROM e2e_certificate_ids)")
            cursor.execute("DELETE FROM certificate_purchase WHERE certificate_id IN (SELECT id FROM e2e_certificate_ids)")
            cursor.execute("UPDATE certificate SET superseded_certificate_id = NULL, replaces_certificate_id = NULL WHERE id IN (SELECT id FROM e2e_certificate_ids)")
            cursor.execute("DELETE FROM certificate WHERE id IN (SELECT id FROM e2e_certificate_ids)")
            cursor.execute("DROP TABLE e2e_certificate_ids")
            cursor.execute("DELETE FROM purchase_invoice WHERE remarks LIKE '%E2E-TEST%'")
            
            # Deleting parent tables after child tables are cleared
            cursor.execute("DELETE FROM party WHERE party_code = 'TST_E2E_PRT'")
            cursor.execute("DELETE FROM stock_movement WHERE material_id IN (SELECT id FROM material WHERE material_code IN ('TST_E2E_RAW', 'TST_E2E_REC'))")
            cursor.execute("DELETE FROM inventory_balance WHERE material_id IN (SELECT id FROM material WHERE material_code IN ('TST_E2E_RAW', 'TST_E2E_REC'))")
            cursor.execute("DELETE FROM material WHERE material_code IN ('TST_E2E_RAW', 'TST_E2E_REC')")
            conn.commit()
        finally:
            conn.close()

    def tearDown(self):
        self.app_context.pop()

    def test_end_to_end_business_scenario(self):
        conn = get_connection()
        try:
            cursor = conn.cursor()
            # Step 1: Create Customer / Party with unique GSTIN to prevent unique conflicts
            cursor.execute(
                """INSERT INTO party (party_code, company_name, party_type, gstin, pan, phone, billing_address, city, state, state_code, pincode)
                   VALUES ('TST_E2E_PRT', 'E2E Test Corp', 'SUPPLIER', '27AAACT0001A9Z9', 'AAACT0001A', '+91 99999 99999', '123 Test Street', 'Mumbai', 'Maharashtra', '27', '400001')"""
            )
            party_id = cursor.lastrowid

            # Insert Materials
            cursor.execute(
                """INSERT INTO material (material_code, material_name, category, hsn_code, uom, gst_percentage, tracking_type)
                   VALUES ('TST_E2E_RAW', 'E2E Raw Scrap', 'Scrap', '1234', 'KG', 18.0, 'BOTH')"""
            )
            raw_mat_id = cursor.lastrowid

            cursor.execute(
                """INSERT INTO material (material_code, material_name, category, hsn_code, uom, gst_percentage, tracking_type)
                   VALUES ('TST_E2E_REC', 'E2E Recovered Metal', 'Recovered', '1234', 'KG', 18.0, 'BOTH')"""
            )
            rec_mat_id = cursor.lastrowid
            conn.commit()
        finally:
            conn.close()

        # Step 2: Create Purchase Invoice
        items = [{
            "material_id": raw_mat_id,
            "qty": 100.0,
            "weight": 100.0,
            "rate": 10.0,
            "amount": 1000.0,
            "gst_percentage": 18.0
        }]
        purchase_id = create_purchase_invoice(
            party_id=party_id,
            invoice_date=date.today().isoformat(),
            supplier_invoice_number="SUPP-E2E-01",
            payment_mode="CASH",
            transporter="Transporter E2E",
            vehicle_number="MH-01-E2E-01",
            remarks="E2E-TEST Inbound Scrap Purchase",
            items=items,
            company_state_code="27",
            party_state_code="27",
            status="CONFIRMED"
        )

        # Step 3: Confirm Purchase & Sync Document
        sync_document("PURCHASE", purchase_id, performed_by="E2E Test Runner")

        # Verify Inventory Increased for raw material
        stock = inventory_repository.get_stock(raw_mat_id, "RAW", 1)
        self.assertEqual(stock["current_quantity"], 100.0)
        self.assertEqual(stock["current_weight"], 100.0)

        # Step 4: Create Processing Job
        job_data = {
            "processing_number": "PJ-E2E-01",
            "processing_date": date.today().isoformat(),
            "priority": "NORMAL",
            "operator_id": "E2E Operator",
            "remarks": "E2E-TEST processing batch",
        }
        inputs = [{
            "material_id": raw_mat_id,
            "quantity": 50.0,
            "weight": 50.0,
            "unit": "KG",
            "inventory_state": "RAW",
            "processing_type": "DISMANTLING"
        }]
        outputs = [{
            "material_id": rec_mat_id,
            "quantity": 45.0,
            "weight": 45.0,
            "unit": "KG",
            "inventory_state": "RECOVERED"
        }]
        losses = [{
            "loss_reason": "DUST",
            "loss_weight": 5.0,
            "remarks": "Process dust scrap loss"
        }]

        job_id = processing_service.create_job(job_data, inputs, "E2E Test Runner")

        # Reserve inventory (by starting the job)
        processing_service.start_job(job_id, "E2E Test Runner")

        # Check stock is reserved
        raw_stock_after_reservation = inventory_repository.get_stock(raw_mat_id, "RAW", 1)
        self.assertEqual(raw_stock_after_reservation["current_quantity"], 50.0)

        reserved_stock = inventory_repository.get_stock(raw_mat_id, "RESERVED", 1)
        self.assertEqual(reserved_stock["current_quantity"], 50.0)

        # Complete processing
        processing_service.complete_job(job_id, outputs, losses, "E2E Test Runner")

        # Verify raw material in processing is consumed (decreased to 0)
        reserved_stock_after = inventory_repository.get_stock(raw_mat_id, "RESERVED", 1)
        self.assertEqual(reserved_stock_after["current_quantity"], 0.0)

        # Verify Recovered inventory created
        recovered_stock = inventory_repository.get_stock(rec_mat_id, "RECOVERED", 1)
        self.assertEqual(recovered_stock["current_quantity"], 45.0)
        self.assertEqual(recovered_stock["current_weight"], 45.0)

        # Step 5: Generate Certificate
        cert_id = certificate_service.create_draft_certificate(
            customer_id=party_id,
            cert_type="RECYCLING",
            template_key="STANDARD",
            job_ids=[job_id],
            purchase_ids=[purchase_id],
            remarks="E2E-TEST compliance certificate",
            performed_by="E2E Test Runner"
        )
        certificate_service.generate_and_lock_certificate(cert_id, "E2E Test Runner")

        # Verify Certificate status and links
        cert = certificate_repository.get_certificate(cert_id)
        self.assertEqual(cert["status"], "LOCKED")
        self.assertEqual(cert["customer_id"], party_id)
        self.assertEqual(len(cert["processing_jobs"]), 1)
        self.assertEqual(len(cert["purchases"]), 1)

        # Step 6: Create Sales Invoice & Confirm Sale
        sales_items = [{
            "material_id": rec_mat_id,
            "inventory_state": "RECOVERED",
            "qty": 20.0,
            "weight": 20.0,
            "rate": 15.0,
            "amount": 300.0,
            "gst_percentage": 18.0
        }]
        sales_id = create_sales_invoice(
            party_id=party_id,
            invoice_date=date.today().isoformat(),
            payment_mode="BANK_TRANSFER",
            transporter="Transporter E2E Sales",
            vehicle_number="MH-01-E2E-02",
            remarks="E2E-TEST Recovered Sales Invoice",
            items=sales_items,
            company_state_code="27",
            party_state_code="27",
            status="CONFIRMED"
        )
        sync_document("SALE", sales_id, performed_by="E2E Test Runner")

        # Verify Recovered inventory reduced
        recovered_stock_final = inventory_repository.get_stock(rec_mat_id, "RECOVERED", 1)
        self.assertEqual(recovered_stock_final["current_quantity"], 25.0)

        # Step 7: Verify Dashboard snapshot
        snapshot = get_dashboard_snapshot()
        self.assertGreaterEqual(snapshot["inventory_items"], 1)

        # Verify recent activities include E2E logs
        activities = get_recent_activities(limit=20)
        actions = [a["action"] for a in activities]
        self.assertTrue(any("Processing Completed" in act for act in actions) or any("Processing Started" in act for act in actions))
        self.assertTrue(any("Create Certificate Draft" in act or "Lock Certificate" in act for act in actions))
