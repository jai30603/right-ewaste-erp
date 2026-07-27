import io
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
from backend.modules.documents.services.document_service import EnterpriseDocumentService
from backend.modules.documents.services.collaboration_governance_service import CollaborationGovernanceService
from backend.app import app

class EDMSCollaborationGovernanceTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        initialize_database()

    def setUp(self):
        self.orig_csrf_bypass = app.config.get("CSRF_BYPASS")
        app.config["CSRF_BYPASS"] = True
        app.config["TESTING"] = True
        self.app = app.test_client()
        self.app.testing = True
        self.doc_service = EnterpriseDocumentService()
        self.collab_service = CollaborationGovernanceService()

    def tearDown(self):
        if self.orig_csrf_bypass is None:
            app.config.pop("CSRF_BYPASS", None)
        else:
            app.config["CSRF_BYPASS"] = self.orig_csrf_bypass

    def test_01_document_sharing(self):
        token = str(uuid.uuid4())[:8]
        doc = self.doc_service.upload_document(io.BytesIO(b"Sharing Test Payload"), f"share_{token}.pdf", user_id=1)

        # Share document
        share = self.collab_service.share_document(doc['id'], shared_with_user_id=1, permission_level='View')
        self.assertEqual(share['document_id'], doc['id'])

        # List shares
        shares = self.collab_service.get_document_shares(doc['id'])
        self.assertTrue(len(shares) >= 1)

        # Revoke share
        rev_ok = self.collab_service.revoke_share(share['id'])
        self.assertTrue(rev_ok)

    def test_02_threaded_comments(self):
        token = str(uuid.uuid4())[:8]
        doc = self.doc_service.upload_document(io.BytesIO(b"Comment Test Payload"), f"comment_{token}.pdf", user_id=1)

        # Add comment
        c1 = self.collab_service.add_comment(doc['id'], "First discussion comment", user_id=1)
        self.assertEqual(c1['comment_text'], "First discussion comment")

        # Reply comment
        c2 = self.collab_service.add_comment(doc['id'], "Reply comment", parent_comment_id=c1['id'], user_id=1)
        self.assertEqual(c2['parent_comment_id'], c1['id'])

        # Fetch comment tree
        tree = self.collab_service.get_document_comments(doc['id'])
        self.assertTrue(len(tree) >= 1)

    def test_03_approval_workflow(self):
        token = str(uuid.uuid4())[:8]
        doc = self.doc_service.upload_document(io.BytesIO(b"Approval Test Payload"), f"appr_{token}.pdf", user_id=1)

        # Submit for approval
        wf = self.collab_service.submit_for_approval(doc['id'], reviewer_id=1)
        self.assertEqual(wf['status'], 'UNDER_REVIEW')

        # Approve
        res = self.collab_service.process_approval_action(wf['id'], action='APPROVE', remarks="Approved by Super Admin")
        self.assertEqual(res['status'], 'APPROVED')

    def test_04_checkout_checkin_locking(self):
        token = str(uuid.uuid4())[:8]
        doc = self.doc_service.upload_document(io.BytesIO(b"Lock Test Payload"), f"lock_{token}.pdf", user_id=1)

        # Check-Out Lock
        lock = self.collab_service.check_out_document(doc['id'], lock_reason="Legal Audit")
        self.assertEqual(lock['is_locked'], 1)

        # Check-In Unlock
        res = self.collab_service.check_in_document(doc['id'], file_stream=io.BytesIO(b"Updated Lock Payload"), filename=f"lock_{token}_v2.pdf")
        self.assertTrue(res['success'])

    def test_05_notifications_and_governance(self):
        # Notifications
        notifs = self.collab_service.get_user_notifications(user_id=1)
        self.assertIsNotNone(notifs)

        # Governance Policies
        pols = self.collab_service.get_governance_policies()
        self.assertTrue(len(pols) >= 4)

        upd = self.collab_service.update_governance_policy('watermark_enabled', True)
        self.assertTrue(upd)

    def test_06_collaboration_web_route_and_apis(self):
        # Web Route
        resp = self.app.get('/documents/collaboration')
        self.assertEqual(resp.status_code, 200)

        # REST APIs
        resp_pols = self.app.get('/api/v1/documents/governance/policies')
        self.assertEqual(resp_pols.status_code, 200)

        resp_notifs = self.app.get('/api/v1/documents/notifications')
        self.assertEqual(resp_notifs.status_code, 200)

if __name__ == '__main__':
    unittest.main()
