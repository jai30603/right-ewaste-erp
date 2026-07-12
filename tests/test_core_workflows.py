import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CoreWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tempdir = tempfile.TemporaryDirectory()
        cls.database = Path(cls.tempdir.name) / "test.db"
        connection = sqlite3.connect(cls.database)
        try:
            for schema_file in sorted((ROOT / "database" / "schema").glob("*.sql")):
                connection.executescript(schema_file.read_text(encoding="utf-8"))
            connection.execute(
                "INSERT INTO company (company_name, address_line_1, city, state, state_code, pincode, gstin, pan, phone) "
                "VALUES ('Right Ewaste', 'Address', 'Mumbai', 'Maharashtra', '27', '400001', '27ABCDE1234F1Z5', 'ABCDE1234F', '9999999999')"
            )
            connection.execute(
                "INSERT INTO material (material_code, material_name, hsn_code, uom, gst_percentage) VALUES ('MAT-1', 'Copper', '7404', 'KG', 5)"
            )
            connection.commit()
        finally:
            connection.close()
        os.environ["RIGHT_EWASTE_DATABASE"] = str(cls.database)
        sys.path.insert(0, str(ROOT / "backend"))
        from app import app

        cls.app = app
        cls.app.config["TESTING"] = True

    @classmethod
    def tearDownClass(cls):
        cls.tempdir.cleanup()

    def test_party_form_validates_and_derives_state_code(self):
        client = self.app.test_client()
        client.get("/party/add")
        with client.session_transaction() as session:
            token = session["csrf_token"]
        response = client.post(
            "/party/add",
            data={
                "csrf_token": token,
                "company_name": "Acme Recycling",
                "contact_person": "Asha",
                "party_type": "CUSTOMER",
                "gstin": "",
                "phone": "9876543210",
                "email": "asha@example.com",
                "billing_address": "Pune",
                "city": "Pune",
                "state": "Maharashtra",
                # This must be ignored; the server derives the trusted code.
                "state_code": "00",
            },
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        connection = sqlite3.connect(self.database)
        try:
            row = connection.execute("SELECT state_code FROM party WHERE company_name = 'Acme Recycling'").fetchone()
        finally:
            connection.close()
        self.assertEqual(row[0], "27")

    def test_invoice_uses_material_gst_and_foreign_keys(self):
        from database import get_connection
        from services.invoice_service import create_sales_invoice

        connection = sqlite3.connect(self.database)
        try:
            connection.execute(
                "INSERT INTO party (party_code, company_name, party_type, phone, billing_address, city, state, state_code) "
                "VALUES ('PTY-90000', 'Buyer', 'CUSTOMER', '8888888888', 'Delhi', 'Delhi', 'Delhi', '07')"
            )
            party_id = connection.execute("SELECT id FROM party WHERE party_code = 'PTY-90000'").fetchone()[0]
            connection.commit()
        finally:
            connection.close()

        connection = get_connection()
        try:
            self.assertEqual(connection.execute("PRAGMA foreign_keys").fetchone()[0], 1)
        finally:
            connection.close()
        invoice_number = create_sales_invoice(party_id, "NEFT", "Self", "MH01AB1234", [{"material_id": 1, "quantity": 2, "rate": 100}])
        connection = sqlite3.connect(self.database)
        try:
            invoice = connection.execute("SELECT subtotal, igst, grand_total FROM sales_invoice WHERE invoice_number = ?", (invoice_number,)).fetchone()
        finally:
            connection.close()
        self.assertEqual(invoice, (200.0, 10.0, 210.0))


if __name__ == "__main__":
    unittest.main()
