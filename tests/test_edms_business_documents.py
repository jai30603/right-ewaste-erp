import io
import os
import sys
import uuid
import unittest
from pathlib import Path

# Adjust python path
BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = BASE_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.database import initialize_database, get_connection
from backend.modules.documents.services.business_document_service import BusinessDocumentService
from backend.modules.documents.services.document_service import EnterpriseDocumentService
from backend.app import app

class EDMSBusinessDocumentsTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        initialize_database()

    def setUp(self):
        self.orig_csrf_bypass = app.config.get("CSRF_BYPASS")
        app.config["CSRF_BYPASS"] = True
        app.config["TESTING"] = True
        self.app = app.test_client()
        self.app.testing = True
        self.biz_doc_service = BusinessDocumentService()
        self.doc_service = EnterpriseDocumentService()

    def tearDown(self):
        if self.orig_csrf_bypass is None:
            app.config.pop("CSRF_BYPASS", None)
        else:
            app.config["CSRF_BYPASS"] = self.orig_csrf_bypass

    def test_01_upload_and_link_document(self):
        token = str(uuid.uuid4())[:8]
        unique_bytes = f"Purchase Invoice Supplier Copy {token}".encode('utf-8')
        file_stream = io.BytesIO(unique_bytes)

        # Upload and link to purchase record #101
        link = self.biz_doc_service.upload_and_link_document(
            file_stream=file_stream,
            original_name=f"purchase_invoice_{token}.pdf",
            module_name="purchase",
            record_id=101,
            record_type="invoice",
            category="Invoice",
            description="Supplier invoice scan"
        )
        self.assertIsNotNone(link['id'])
        self.assertEqual(link['module_name'], 'purchase')
        self.assertEqual(link['record_id'], 101)
        self.assertEqual(link['category'], 'Invoice')

    def test_02_store_generated_pdf(self):
        token = str(uuid.uuid4())[:8]
        fake_pdf_bytes = f"%PDF-1.4 Generated Certificate PDF {token}".encode('utf-8')

        # Store generated PDF for certificate record #202
        link = self.biz_doc_service.store_and_link_generated_pdf(
            pdf_bytes=fake_pdf_bytes,
            filename=f"certificate_{token}.pdf",
            module_name="certificate",
            record_id=202,
            category="Certificate"
        )
        self.assertIsNotNone(link['id'])
        self.assertEqual(link['module_name'], 'certificate')
        self.assertEqual(link['record_id'], 202)

    def test_03_query_record_documents_and_timeline(self):
        rec_id = 999
        unique_bytes = b"Employee Resume File Payload"
        link1 = self.biz_doc_service.upload_and_link_document(
            io.BytesIO(unique_bytes), "resume.pdf", "employee", rec_id, category="Technical"
        )

        docs = self.biz_doc_service.get_record_documents("employee", rec_id)
        self.assertTrue(len(docs) > 0)

        timeline = self.biz_doc_service.get_record_document_timeline("employee", rec_id)
        self.assertTrue(len(timeline) > 0)

        # Unlink document
        unlink_ok = self.biz_doc_service.unlink_document_from_record(link1['id'])
        self.assertTrue(unlink_ok)

    def test_04_attachment_rest_apis(self):
        token = str(uuid.uuid4())[:8]
        api_bytes = f"API Upload payload {token}".encode('utf-8')

        # Test REST API upload and link
        resp = self.app.post(
            '/api/v1/documents/attachments/upload-and-link',
            data={
                'file': (io.BytesIO(api_bytes), f"api_doc_{token}.pdf"),
                'module_name': 'sales',
                'record_id': 303,
                'category': 'Quotation'
            }
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.get_json()
        self.assertTrue(data['success'])
        link_id = data['attachment']['id']

        # Test REST API fetch record attachments
        resp_fetch = self.app.get('/api/v1/documents/attachments/sales/303')
        self.assertEqual(resp_fetch.status_code, 200)
        self.assertTrue(resp_fetch.get_json()['success'])

        # Test REST API unlink
        resp_del = self.app.delete(f'/api/v1/documents/attachments/{link_id}')
        self.assertEqual(resp_del.status_code, 200)

if __name__ == '__main__':
    unittest.main()
