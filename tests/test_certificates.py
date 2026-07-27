import sys
import unittest
import sqlite3
import os
import hashlib
from pathlib import Path
from datetime import date

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "backend"))
sys.path.insert(0, str(BASE_DIR))

from database import get_connection
from services import certificate_service, processing_service
from repositories import certificate_repository, party_repository
from services.inventory_service import record_movement
from app import app

class CertificatesTest(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config["TESTING"] = True
        self.app_context = self.app.test_request_context()
        self.app_context.push()
        
        self.conn = get_connection()
        cursor = self.conn.cursor()
        
        # Clean up potential leftovers from previous failed setups in correct dependency order
        cursor.execute("DELETE FROM certificate_processing WHERE processing_job_id IN (SELECT id FROM processing_job WHERE processing_number = 'PJ-TEST-CERT-01')")
        cursor.execute("DELETE FROM certificate WHERE remarks LIKE '%Test Suite%'")
        cursor.execute("DELETE FROM processing_input WHERE material_id IN (SELECT id FROM material WHERE material_code IN ('T_RAW_C1', 'T_OUT_C1'))")
        cursor.execute("DELETE FROM processing_output WHERE material_id IN (SELECT id FROM material WHERE material_code IN ('T_RAW_C1', 'T_OUT_C1'))")
        cursor.execute("DELETE FROM processing_loss WHERE processing_job_id IN (SELECT id FROM processing_job WHERE processing_number = 'PJ-TEST-CERT-01')")
        cursor.execute("DELETE FROM processing_job WHERE processing_number = 'PJ-TEST-CERT-01'")
        cursor.execute("DELETE FROM purchase_invoice_item WHERE purchase_invoice_id IN (SELECT id FROM purchase_invoice WHERE purchase_invoice_number = 'PUR-TEST-CERT-01')")
        cursor.execute("DELETE FROM purchase_invoice WHERE purchase_invoice_number = 'PUR-TEST-CERT-01'")
        cursor.execute("DELETE FROM party WHERE party_code = 'TST_PRT_C1'")
        cursor.execute("DELETE FROM stock_movement WHERE material_id IN (SELECT id FROM material WHERE material_code IN ('T_RAW_C1', 'T_OUT_C1'))")
        cursor.execute("DELETE FROM inventory_balance WHERE material_id IN (SELECT id FROM material WHERE material_code IN ('T_RAW_C1', 'T_OUT_C1'))")
        cursor.execute("DELETE FROM material WHERE material_code IN ('T_RAW_C1', 'T_OUT_C1')")
        self.conn.commit()
        
        # 1. Create a test Party (Customer) with address and GSTIN
        cursor.execute(
            """INSERT INTO party (party_code, company_name, party_type, gstin, pan, phone, billing_address, city, state, state_code, pincode)
               VALUES ('TST_PRT_C1', 'Test Customer Corp', 'SUPPLIER', '27AAACT0001A1Z1', 'AAACT0001A', '+91 99999 99999', '123 Test Street', 'Mumbai', 'Maharashtra', '27', '400001')"""
        )
        self.party_id = cursor.lastrowid
        
        # 2. Create test materials
        cursor.execute(
            """INSERT INTO material (material_code, material_name, category, hsn_code, uom, gst_percentage, tracking_type)
               VALUES ('T_RAW_C1', 'Test Raw Certificate', 'Scrap', '1234', 'KG', 18.0, 'BOTH')"""
        )
        self.raw_material_id = cursor.lastrowid

        cursor.execute(
            """INSERT INTO material (material_code, material_name, category, hsn_code, uom, gst_percentage, tracking_type)
               VALUES ('T_OUT_C1', 'Test Out Certificate', 'Recovered', '1234', 'KG', 18.0, 'BOTH')"""
        )
        self.out_material_id = cursor.lastrowid

        # 3. Create test Purchase Invoice
        cursor.execute(
            """INSERT INTO purchase_invoice (purchase_invoice_number, invoice_date, supplier_id, subtotal, grand_total, status, is_active)
               VALUES ('PUR-TEST-CERT-01', '2026-07-16', ?, 1000.0, 1000.0, 'CONFIRMED', 1)""",
            (self.party_id,)
        )
        self.purchase_id = cursor.lastrowid
        
        self.conn.commit()

        # 4. Bootstrap raw stock
        record_movement(
            material_id=self.raw_material_id,
            movement_type="PURCHASE",
            reference_type="PURCHASE_INVOICE",
            reference_number=str(self.purchase_id),
            quantity_change=100.0,
            weight_change=100.0,
            inventory_state="RAW",
            performed_by="Test Suite Certs"
        )

        # 5. Create a Processing Job and COMPLETE it
        job_data = {
            "processing_number": "PJ-TEST-CERT-01",
            "processing_date": "2026-07-16",
            "priority": "HIGH",
            "operator_id": "Test Operator",
            "remarks": "Test Suite Job Details",
        }
        inputs = [{
            "material_id": self.raw_material_id,
            "quantity": 50.0,
            "weight": 50.0,
            "unit": "KG",
            "processing_type": "DISMANTLING",
            "inventory_reference": str(self.purchase_id)
        }]
        self.job_id = processing_service.create_job(job_data, inputs, "Test Suite Certs")
        
        # Start and complete the job
        processing_service.start_job(self.job_id, "Test Suite Certs")
        
        outputs = [{
            "material_id": self.out_material_id,
            "quantity": 48.0,
            "weight": 48.0,
            "unit": "KG",
            "inventory_state": "RECOVERED"
        }]
        losses = [{
            "loss_reason": "WATER",
            "loss_weight": 2.0
        }]
        processing_service.complete_job(self.job_id, outputs, losses, "Test Suite Certs")

    def tearDown(self):
        cursor = self.conn.cursor()
        
        # Delete generated test certificates and links
        cursor.execute("DELETE FROM certificate_processing WHERE processing_job_id = ?", (self.job_id,))
        cursor.execute("DELETE FROM certificate WHERE remarks LIKE '%Test Suite%'")
        cursor.execute("DELETE FROM processing_job WHERE id = ?", (self.job_id,))
        cursor.execute("DELETE FROM purchase_invoice WHERE id = ?", (self.purchase_id,))
        cursor.execute("DELETE FROM party WHERE id = ?", (self.party_id,))
        cursor.execute("DELETE FROM stock_movement WHERE performed_by = 'Test Suite Certs'")
        cursor.execute("DELETE FROM inventory_balance WHERE material_id IN (?, ?)", (self.raw_material_id, self.out_material_id))
        cursor.execute("DELETE FROM material WHERE id IN (?, ?)", (self.raw_material_id, self.out_material_id))
        
        self.conn.commit()
        self.conn.close()
        
        # Pop the context safely
        self.app_context.pop()

    def test_certificate_lifecycle(self):
        # 1. Check eligibility queue
        eligible = certificate_repository.get_eligible_processing_jobs()
        match_job = next((j for j in eligible if j["id"] == self.purchase_id), None)
        self.assertIsNotNone(match_job)
        self.assertEqual(match_job["readiness"], "Ready for Certificate")
        self.assertEqual(match_job["customer_id"], self.party_id)

        # 2. Generate certificate series numbering format
        number = certificate_service.generate_certificate_number()
        self.assertTrue(number.startswith(f"CERT-{date.today().year}-"))

        # 3. Create Draft Certificate
        cert_id = certificate_service.create_draft_certificate(
            customer_id=self.party_id,
            cert_type="RECYCLING",
            template_key="STANDARD",
            job_ids=[self.job_id],
            purchase_ids=[self.purchase_id],
            remarks="Test Suite Draft Verification",
            performed_by="Test Suite Certs"
        )
        self.assertIsNotNone(cert_id)

        cert = certificate_repository.get_certificate(cert_id)
        self.assertEqual(cert["status"], "DRAFT")
        self.assertEqual(cert["customer_id"], self.party_id)
        self.assertEqual(len(cert["processing_jobs"]), 1)
        self.assertEqual(len(cert["purchases"]), 1)

        # 4. Generate and Lock
        certificate_service.generate_and_lock_certificate(cert_id, "Test Suite Certs")
        cert = certificate_repository.get_certificate(cert_id)
        self.assertEqual(cert["status"], "LOCKED")
        self.assertEqual(len(cert["pdfs"]), 1)

        # 5. Correct/Supersede Certificate
        new_cert_id = certificate_service.supersede_certificate(
            cert_id=cert_id,
            template_key="CORPORATE",
            remarks="Test Suite Corrective Replacement",
            performed_by="Test Suite Certs"
        )
        self.assertIsNotNone(new_cert_id)

        # Check old certificate is now SUPERSEDED
        old_cert = certificate_repository.get_certificate(cert_id)
        self.assertEqual(old_cert["status"], "SUPERSEDED")
        self.assertEqual(old_cert["superseded_certificate_id"], new_cert_id)

        # Check replacement certificate details
        new_cert = certificate_repository.get_certificate(new_cert_id)
        self.assertEqual(new_cert["status"], "LOCKED")
        self.assertEqual(new_cert["replaces_certificate_id"], cert_id)
        self.assertEqual(new_cert["version_number"], 2)

        # 6. Cancel replacement certificate
        certificate_service.cancel_certificate(new_cert_id, "Test Cancel Reason", "Test Suite Certs")
        cancelled_cert = certificate_repository.get_certificate(new_cert_id)
        self.assertEqual(cancelled_cert["status"], "CANCELLED")
        self.assertEqual(cancelled_cert["cancellation_reason"], "Test Cancel Reason")
        self.assertEqual(cancelled_cert["cancelled_by"], "Test Suite Certs")

if __name__ == "__main__":
    unittest.main()
