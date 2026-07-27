import unittest
from datetime import date

from backend.app import app
from backend.database import get_connection
from backend.repositories.inventory_repository import get_stock


class PurchaseInventoryFlowTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.previous_auth_required = app.config["ERP_AUTH_REQUIRED"]
        app.config["ERP_AUTH_REQUIRED"] = False

        conn = get_connection()
        try:
            cursor = conn.cursor()
            # Pre-cleanup in case previous tearDown failed
            stale_invoices = [row[0] for row in cursor.execute(
                "SELECT id FROM purchase_invoice WHERE supplier_invoice_number = 'TST-PUR-FLOW'"
            )]
            for inv_id in stale_invoices:
                cursor.execute("DELETE FROM stock_movement WHERE reference_type = 'PURCHASE' AND reference_id = ?", (inv_id,))
                cursor.execute("DELETE FROM material_batch WHERE purchase_invoice_id = ?", (inv_id,))
                cursor.execute("DELETE FROM purchase_invoice_item WHERE purchase_invoice_id = ?", (inv_id,))
                cursor.execute("DELETE FROM purchase_invoice WHERE id = ?", (inv_id,))
            stale_mat = cursor.execute("SELECT id FROM material WHERE material_code = 'TST_PUR_FLOW'").fetchone()
            if stale_mat:
                cursor.execute("DELETE FROM inventory_balance WHERE material_id = ?", (stale_mat[0],))
                cursor.execute("DELETE FROM material_batch WHERE material_id = ?", (stale_mat[0],))
                cursor.execute("DELETE FROM material WHERE id = ?", (stale_mat[0],))
            cursor.execute("DELETE FROM party WHERE party_code = 'TST_PUR_FLOW'")
            conn.commit()

            cursor.execute(
                """INSERT INTO party (
                    party_code, company_name, party_type, phone, billing_address, city, state, state_code
                ) VALUES ('TST_PUR_FLOW', 'Purchase Flow Supplier', 'SUPPLIER', '9999999999',
                          'Test address', 'Mumbai', 'Maharashtra', '27')"""
            )
            self.party_id = cursor.lastrowid
            cursor.execute(
                """INSERT INTO material (
                    material_code, material_name, category, hsn_code, uom, gst_percentage, tracking_type
                ) VALUES ('TST_PUR_FLOW', 'Purchase Flow Material', 'Scrap', '8471', 'KG', 18, 'BOTH')"""
            )
            self.material_id = cursor.lastrowid
            conn.commit()
        finally:
            conn.close()

    def tearDown(self):
        conn = get_connection()
        try:
            invoice_ids = [row[0] for row in conn.execute(
                "SELECT id FROM purchase_invoice WHERE supplier_invoice_number = 'TST-PUR-FLOW'"
            )]
            for invoice_id in invoice_ids:
                conn.execute("DELETE FROM stock_movement WHERE reference_type = 'PURCHASE' AND reference_id = ?", (invoice_id,))
                conn.execute("DELETE FROM material_batch WHERE purchase_invoice_id = ?", (invoice_id,))
                conn.execute("DELETE FROM purchase_invoice_item WHERE purchase_invoice_id = ?", (invoice_id,))
                conn.execute("DELETE FROM purchase_invoice WHERE id = ?", (invoice_id,))
            conn.execute("DELETE FROM inventory_balance WHERE material_id = ?", (self.material_id,))
            conn.execute("DELETE FROM activity_log WHERE details LIKE '%TST-PUR-FLOW%'")
            conn.execute("DELETE FROM material WHERE id = ?", (self.material_id,))
            conn.execute("DELETE FROM party WHERE id = ?", (self.party_id,))
            conn.commit()
        finally:
            conn.close()
            app.config["ERP_AUTH_REQUIRED"] = self.previous_auth_required

    def test_purchase_creation_syncs_inventory_and_activity_log(self):
        self.client.get("/purchase/add")
        with self.client.session_transaction() as session:
            csrf_token = session["_csrf_token"]

        response = self.client.post(
            "/purchase/add",
            data={
                "_csrf_token": csrf_token,
                "supplier_id": str(self.party_id),
                "invoice_date": date.today().isoformat(),
                "supplier_invoice_number": "TST-PUR-FLOW",
                "payment_mode": "Cash",
                "status": "CONFIRMED",
                "intake_type": "Purchase",
                "material_id[]": str(self.material_id),
                "qty[]": "4",
                "weight[]": "12.5",
                "rate[]": "10",
                "amount[]": "40",
                "gst_percentage[]": "18",
            },
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)
        stock = get_stock(self.material_id, "RAW")
        self.assertEqual(stock["current_quantity"], 4.0)
        self.assertEqual(stock["current_weight"], 12.5)

        conn = get_connection()
        try:
            activity = conn.execute(
                "SELECT action FROM activity_log WHERE details LIKE '%TST-PUR-FLOW%' ORDER BY id DESC LIMIT 1"
            ).fetchone()
        finally:
            conn.close()
        self.assertIsNotNone(activity)
        self.assertEqual(activity[0], "Create Purchase Invoice")


if __name__ == "__main__":
    unittest.main()
