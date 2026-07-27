import sys
import unittest
import sqlite3
from pathlib import Path
from datetime import date

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "backend"))
sys.path.insert(0, str(BASE_DIR))

from database import get_connection
from services import processing_service
from repositories import processing_repository, inventory_repository
from services.inventory_service import record_movement

class MaterialProcessingTest(unittest.TestCase):
    def setUp(self):
        # We will create a test material and add some RAW stock
        self.conn = get_connection()
        cursor = self.conn.cursor()
        
        # Insert test raw material
        cursor.execute(
            """INSERT INTO material (material_code, material_name, category, hsn_code, uom, gst_percentage, tracking_type)
               VALUES ('TST_RAW_01', 'Test Raw Material', 'Scrap', '1234', 'KG', 18.0, 'BOTH')"""
        )
        self.raw_material_id = cursor.lastrowid
        
        # Insert test output material
        cursor.execute(
            """INSERT INTO material (material_code, material_name, category, hsn_code, uom, gst_percentage, tracking_type)
               VALUES ('TST_OUT_01', 'Test Output Material', 'Recovered', '1234', 'KG', 18.0, 'BOTH')"""
        )
        self.out_material_id = cursor.lastrowid
        
        self.conn.commit()
        
        # Add stock to RAW
        record_movement(
            material_id=self.raw_material_id,
            movement_type="PURCHASE",
            reference_type="PURCHASE_INVOICE",
            reference_number="TEST-PUR-01",
            quantity_change=100.0,
            weight_change=100.0,
            inventory_state="RAW",
            performed_by="Test Suite"
        )

    def tearDown(self):
        # Clean up database entries
        cursor = self.conn.cursor()
        
        # Delete created jobs and actions will cascade
        cursor.execute("DELETE FROM processing_job WHERE remarks LIKE '%Test Suite%'")
        cursor.execute("DELETE FROM stock_movement WHERE performed_by = 'Test Suite'")
        cursor.execute("DELETE FROM inventory_balance WHERE material_id IN (?, ?)", (self.raw_material_id, self.out_material_id))
        cursor.execute("DELETE FROM material WHERE id IN (?, ?)", (self.raw_material_id, self.out_material_id))
        
        self.conn.commit()
        self.conn.close()

    def test_job_lifecycle_and_validation(self):
        # 1. Generate unique sequential PJ number
        pj_num = processing_service.generate_job_number()
        self.assertTrue(pj_num.startswith(f"PJ-{date.today().year}-"))

        # 2. Create job in Draft
        job_data = {
            "processing_number": "",
            "processing_date": date.today().strftime("%Y-%m-%d"),
            "priority": "HIGH",
            "operator_id": "Test Operator",
            "remarks": "Test Suite Job Details",
        }
        inputs = [{
            "material_id": self.raw_material_id,
            "quantity": 20.0,
            "weight": 20.0,
            "unit": "KG",
            "processing_type": "DISMANTLING",
            "inventory_reference": None
        }]
        
        job_id = processing_service.create_job(job_data, inputs, "Test Suite")
        self.assertIsNotNone(job_id)
        
        # Check stock is NOT reserved yet (RAW should still be 100, RESERVED should be 0)
        stock_raw = inventory_repository.get_stock(self.raw_material_id, "RAW", 1, self.conn)
        stock_res = inventory_repository.get_stock(self.raw_material_id, "RESERVED", 1, self.conn)
        self.assertEqual(stock_raw["current_quantity"], 100.0)
        self.assertEqual(stock_res["current_quantity"], 0.0)

        # 3. Start Job: Check stock moves from RAW to RESERVED
        processing_service.start_job(job_id, "Test Suite")
        
        stock_raw = inventory_repository.get_stock(self.raw_material_id, "RAW", 1, self.conn)
        stock_res = inventory_repository.get_stock(self.raw_material_id, "RESERVED", 1, self.conn)
        self.assertEqual(stock_raw["current_quantity"], 80.0)
        self.assertEqual(stock_res["current_quantity"], 20.0)
        
        # 4. Weight Validation Balance check
        outputs = [{
            "material_id": self.out_material_id,
            "quantity": 18.0,
            "weight": 18.0,
            "unit": "KG",
            "inventory_state": "RECOVERED",
            "recovered_from_material_id": self.raw_material_id
        }]
        # Loss is 1.0 (total = 19.0, input = 20.0, diff = 1.0 > 0.5 tolerance)
        losses_unbalanced = [{
            "loss_weight": 1.0,
            "loss_reason": "WATER",
            "remarks": "Test Loss Unbalanced"
        }]
        
        with self.assertRaises(ValueError):
            processing_service.complete_job(job_id, outputs, losses_unbalanced, "Test Suite")

        # Balanced loss: 2.0 (total = 20.0, matches input)
        losses_balanced = [{
            "loss_weight": 2.0,
            "loss_reason": "WATER",
            "remarks": "Test Loss Balanced"
        }]
        
        # Complete job
        processing_service.complete_job(job_id, outputs, losses_balanced, "Test Suite")
        
        # Check job status is COMPLETED
        job = processing_repository.get_processing_job(job_id)
        self.assertEqual(job["status"], "COMPLETED")
        
        # Check RESERVED stock is consumed (should be 0) and output stock is created (should be 18.0 in RECOVERED)
        stock_res = inventory_repository.get_stock(self.raw_material_id, "RESERVED", 1, self.conn)
        stock_out = inventory_repository.get_stock(self.out_material_id, "RECOVERED", 1, self.conn)
        self.assertEqual(stock_res["current_quantity"], 0.0)
        self.assertEqual(stock_out["current_quantity"], 18.0)

        # 5. Duplicate job
        new_job_id = processing_service.duplicate_job(job_id, "Test Suite")
        new_job = processing_repository.get_processing_job(new_job_id)
        self.assertEqual(new_job["status"], "DRAFT")
        self.assertEqual(len(new_job["inputs"]), 1)
        self.assertEqual(len(new_job["outputs"]), 1)
        self.assertEqual(len(new_job["losses"]), 1)

        # 6. Reopen Completed Job (Admin role)
        processing_service.reopen_job(job_id, "Test Suite", "admin")
        
        # Check status transited back to IN_PROGRESS
        job = processing_repository.get_processing_job(job_id)
        self.assertEqual(job["status"], "IN_PROGRESS")
        
        # Check stock: outputs subtracted (0), inputs returned to RESERVED (20.0)
        stock_res = inventory_repository.get_stock(self.raw_material_id, "RESERVED", 1, self.conn)
        stock_out = inventory_repository.get_stock(self.out_material_id, "RECOVERED", 1, self.conn)
        self.assertEqual(stock_res["current_quantity"], 20.0)
        self.assertEqual(stock_out["current_quantity"], 0.0)

if __name__ == "__main__":
    unittest.main()
