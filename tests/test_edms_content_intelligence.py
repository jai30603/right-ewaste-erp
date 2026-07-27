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
from backend.modules.documents.services.content_intelligence_service import ContentIntelligenceService
from backend.modules.documents.services.document_service import EnterpriseDocumentService
from backend.app import app

class EDMSContentIntelligenceTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        initialize_database()

    def setUp(self):
        self.orig_csrf_bypass = app.config.get("CSRF_BYPASS")
        app.config["CSRF_BYPASS"] = True
        app.config["TESTING"] = True
        self.app = app.test_client()
        self.app.testing = True
        self.intel_service = ContentIntelligenceService()
        self.doc_service = EnterpriseDocumentService()

    def tearDown(self):
        if self.orig_csrf_bypass is None:
            app.config.pop("CSRF_BYPASS", None)
        else:
            app.config["CSRF_BYPASS"] = self.orig_csrf_bypass

    def test_01_version_control_and_restoration(self):
        token = str(uuid.uuid4())[:8]
        v1_bytes = f"Original Version 1 {token}".encode('utf-8')
        doc = self.doc_service.upload_document(io.BytesIO(v1_bytes), f"contract_{token}.pdf", user_id=1)

        # Upload Version 2
        v2_bytes = f"Updated Version 2 {token}".encode('utf-8')
        doc_v2 = self.intel_service.create_new_version(
            document_id=doc['id'],
            file_stream=io.BytesIO(v2_bytes),
            changelog_notes="Added clause 4B",
            user_id=1
        )
        self.assertEqual(doc_v2['version'], 2)

        # Retrieve version history
        history = self.intel_service.get_version_history(doc['id'])
        self.assertTrue(len(history) >= 2)

        # Restore V1
        restore_ok = self.intel_service.restore_version(doc['id'], version_number=1, user_id=1)
        self.assertTrue(restore_ok)

    def test_02_tagging_and_classification(self):
        token = str(uuid.uuid4())[:8]
        doc = self.doc_service.upload_document(io.BytesIO(b"Tag Test Payload"), f"tag_test_{token}.pdf", user_id=1)

        # Add tag
        tag = self.intel_service.add_tag_to_document(doc['id'], f"Tag_{token}")
        self.assertIsNotNone(tag['id'])

        doc_tags = self.intel_service.get_document_tags(doc['id'])
        tag_names = [t['tag_name'] for t in doc_tags]
        self.assertIn(f"Tag_{token}", tag_names)

        # Update classification & lifecycle
        cls_ok = self.intel_service.update_classification(doc['id'], 'CONFIDENTIAL')
        self.assertTrue(cls_ok)

        lc_ok = self.intel_service.update_lifecycle_status(doc['id'], 'APPROVED')
        self.assertTrue(lc_ok)

    def test_03_document_relationships_and_unified_search(self):
        token = str(uuid.uuid4())[:8]
        doc1 = self.doc_service.upload_document(io.BytesIO(b"Invoice Payload"), f"invoice_{token}.pdf", user_id=1)
        doc2 = self.doc_service.upload_document(io.BytesIO(b"Receipt Payload"), f"receipt_{token}.pdf", user_id=1)

        # Link relationship
        rel_ok = self.intel_service.link_document_relationship(doc1['id'], doc2['id'], 'Invoice-Receipt', 'Linked receipt')
        self.assertTrue(rel_ok)

        rels = self.intel_service.get_document_relationships(doc1['id'])
        self.assertTrue(len(rels) > 0)

        # Unified Intelligent Search
        results = self.intel_service.unified_search(query=token)
        result_ids = [r['id'] for r in results]
        self.assertIn(doc1['id'], result_ids)
        self.assertIn(doc2['id'], result_ids)

    def test_04_web_route_and_intel_apis(self):
        # Web Route
        resp_web = self.app.get('/documents/search')
        self.assertEqual(resp_web.status_code, 200)

        # Search API
        resp_search = self.app.get('/api/v1/documents/intelligence/search')
        self.assertEqual(resp_search.status_code, 200)
        self.assertTrue(resp_search.get_json()['success'])

        # All Tags API
        resp_tags = self.app.get('/api/v1/documents/tags')
        self.assertEqual(resp_tags.status_code, 200)
        self.assertTrue(resp_tags.get_json()['success'])

if __name__ == '__main__':
    unittest.main()
