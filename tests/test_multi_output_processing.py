import sys
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from database import initialize_database, get_connection
from repositories import processing_repository, inventory_repository, disposal_repository, material_repository
from services import processing_service


class TestMultiOutputClassificationAndDisposal(unittest.TestCase):

    def setUp(self):
        initialize_database()
        conn = get_connection()
        try:
            cursor = conn.cursor()
            # Clean test data
            cursor.execute("DELETE FROM disposal_queue WHERE processing_number LIKE 'TEST-JOB-%'")
            cursor.execute("DELETE FROM processing_job WHERE processing_number LIKE 'TEST-JOB-%'")
            conn.commit()
        finally:
            conn.close()

    def test_multi_output_classification_and_disposal_queue(self):
        # 1. Create a Test Processing Job
        job_data = {
            "processing_number": "TEST-JOB-9999",
            "processing_date": "2026-07-23",
            "priority": "HIGH",
            "operator_id": "Operator Alpha",
            "remarks": "Test dismantling 100 Desktop Computers"
        }

        # Select materials for input and outputs
        all_materials = material_repository.get_all_materials()
        self.assertTrue(len(all_materials) >= 4, "Need at least 4 materials in DB")

        input_mat = all_materials[0]
        rec_mat = all_materials[1]
        ref_mat = all_materials[2]
        disp_mat = all_materials[3]

        inputs = [{
            "material_id": input_mat["id"],
            "quantity": 10,
            "weight": 100.0,
            "unit": "KGS",
            "processing_type": "DISMANTLING"
        }]

        # Set up initial RAW inventory for input material so reservation succeeds
        import uuid
        conn = get_connection()
        try:
            inventory_repository.apply_movement({
                "movement_key": f"SETUP_RAW:{uuid.uuid4()}",
                "material_id": input_mat["id"],
                "warehouse_id": 1,
                "inventory_state": "RAW",
                "movement_type": "MANUAL_ADJUSTMENT",
                "reference_type": "TEST",
                "reference_id": 1,
                "reference_number": "INIT-001",
                "quantity_change": 10,
                "weight_change": 100.0,
                "performed_by": "Test Setup"
            }, conn)
            conn.commit()
        finally:
            conn.close()

        # Create Job
        job_id = processing_service.create_job(job_data, inputs, "Test Setup")
        self.assertIsNotNone(job_id)

        # Start Job (reserves inventory)
        processing_service.start_job(job_id, "Test Setup")

        # Define Classified Outputs
        outputs = [
            {
                "material_id": rec_mat["id"],
                "quantity": 5,
                "weight": 45.0,
                "unit": "KGS",
                "output_category": "RECOVERABLE"
            },
            {
                "material_id": ref_mat["id"],
                "quantity": 3,
                "weight": 35.0,
                "unit": "KGS",
                "output_category": "REFURBISHABLE"
            },
            {
                "material_id": disp_mat["id"],
                "quantity": 2,
                "weight": 20.0,
                "unit": "KGS",
                "output_category": "DISPOSAL"
            }
        ]

        # Complete Job (routes outputs & populates Disposal Queue)
        processing_service.complete_job(job_id, outputs, [], "Test Setup")

        # Verify Job Status
        completed_job = processing_repository.get_processing_job(job_id)
        self.assertEqual(completed_job["status"], "COMPLETED")

        # Verify Automatic Disposal Queue Entry Creation
        pending_queue = disposal_repository.get_pending_disposal_queue(query=completed_job["processing_number"])
        self.assertEqual(len(pending_queue), 1, "Disposal output must automatically create 1 Disposal Queue entry")
        
        queue_item = pending_queue[0]
        self.assertEqual(queue_item["processing_number"], completed_job["processing_number"])
        self.assertEqual(queue_item["material_id"], disp_mat["id"])
        self.assertEqual(queue_item["weight"], 20.0)
        self.assertEqual(queue_item["status"], "Pending")

        # Verify Disposal Execution Workflow
        disposal_types = disposal_repository.get_all_disposal_types()
        self.assertTrue(len(disposal_types) > 0, "Disposal types master should be populated")

        disposal_repository.execute_disposal_item(
            queue_id=queue_item["id"],
            disposal_type=disposal_types[0]["type_name"],
            vendor_id=None,
            vendor_name="EcoRecycle Solutions",
            transport_details="MH-04-TR-9988",
            document_path="/static/uploads/disposal/doc1.pdf",
            remarks="Disposed successfully",
            disposed_by="Test Operator"
        )

        # Verify Queue Item Status updated to Disposed
        updated_item = disposal_repository.get_disposal_queue_item(queue_item["id"])
        self.assertEqual(updated_item["status"], "Disposed")
        self.assertEqual(updated_item["disposal_type"], disposal_types[0]["type_name"])
        self.assertEqual(updated_item["vendor_name"], "EcoRecycle Solutions")

    def test_disposal_masters_seeding(self):
        materials = disposal_repository.get_all_disposal_materials()
        self.assertTrue(len(materials) >= 15, "Default disposal materials should be seeded")
        
        types = disposal_repository.get_all_disposal_types()
        self.assertTrue(len(types) >= 8, "Default disposal types should be seeded")


if __name__ == "__main__":
    unittest.main()
