import unittest
import io
import json
import uuid
import sqlite3
from typing import Dict, Any
from backend.app import app
from backend.database import get_connection, initialize_database
from backend.modules.documents.services.document_service import EnterpriseDocumentService
from backend.routes.documents import has_document_access

class EDMSChatFilesTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        initialize_database()
        cls.doc_service = EnterpriseDocumentService()
        cls.app = app.test_client()

    def setUp(self):
        # Empty all chat file reference tables and mock records to start fresh
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys = OFF;")
            cursor.execute("DELETE FROM chat_file_reference")
            cursor.execute("DELETE FROM conversation_attachment")
            cursor.execute("DELETE FROM attachment_metadata")
            cursor.execute("DELETE FROM shared_resources WHERE resource_type = 'DOCUMENT'")
            cursor.execute("DELETE FROM resource_references WHERE resource_type = 'DOCUMENT'")
            cursor.execute("DELETE FROM document_references")
            
            # Setup a couple of test conversations
            # Direct conversation between user 1 and user 2
            cursor.execute("INSERT OR IGNORE INTO conversations (id, type, status) VALUES (101, 'DIRECT', 'ACTIVE')")
            cursor.execute("INSERT OR IGNORE INTO conversation_participants (conversation_id, user_id, status) VALUES (101, 1, 'ACTIVE')")
            cursor.execute("INSERT OR IGNORE INTO conversation_participants (conversation_id, user_id, status) VALUES (101, 2, 'ACTIVE')")
            
            # Group conversation with user 1 and user 3
            cursor.execute("INSERT OR IGNORE INTO conversations (id, type, name, status) VALUES (102, 'GROUP', 'Procurement Group', 'ACTIVE')")
            cursor.execute("INSERT OR IGNORE INTO conversation_participants (conversation_id, user_id, status) VALUES (102, 1, 'ACTIVE')")
            cursor.execute("INSERT OR IGNORE INTO conversation_participants (conversation_id, user_id, status) VALUES (102, 3, 'ACTIVE')")
            
            cursor.execute("PRAGMA foreign_keys = ON;")
            conn.commit()
        finally:
            conn.close()

    def test_01_upload_via_chat_registers_references(self):
        """Verify that uploading a file in chat registers references in all metadata tables."""
        # Call the endpoint to upload a file in conversation 101 as user 1
        with self.app.session_transaction() as sess:
            sess['user'] = {'user_id': 1, 'role': 'User', 'username': 'user1'}
            
        file_data = {
            'file': (io.BytesIO(b"Purchase order details"), 'PO_1001.pdf')
        }
        response = self.app.post('/api/v1/communication/conversations/101/upload-to-edms', data=file_data)
        self.assertEqual(response.status_code, 201)
        res_json = response.get_json()
        self.assertTrue(res_json['success'])
        doc_id = res_json['document_id']
        msg_id = res_json['message_id']

        # Query database to check references
        conn = get_connection()
        try:
            cursor = conn.cursor()
            
            # 1. chat_file_reference
            cursor.execute("SELECT * FROM chat_file_reference WHERE document_id = ?", (doc_id,))
            cfr = cursor.fetchone()
            self.assertIsNotNone(cfr)
            self.assertEqual(cfr['message_id'], msg_id)
            self.assertEqual(cfr['conversation_id'], 101)
            self.assertEqual(cfr['sender_id'], 1)
            
            # 2. conversation_attachment
            cursor.execute("SELECT * FROM conversation_attachment WHERE document_id = ?", (doc_id,))
            ca = cursor.fetchone()
            self.assertIsNotNone(ca)
            self.assertEqual(ca['conversation_id'], 101)
            
            # 3. attachment_metadata
            cursor.execute("SELECT * FROM attachment_metadata WHERE document_id = ?", (doc_id,))
            am = cursor.fetchone()
            self.assertIsNotNone(am)
            self.assertEqual(am['file_type'], 'pdf')
            self.assertEqual(am['file_size'], len(b"Purchase order details"))
        finally:
            conn.close()

    def test_02_sharing_existing_document_registers_references(self):
        """Verify sharing an existing EDMS file registers references without duplicate uploads."""
        # 1. Create a document in My Drive (repository 1)
        doc = self.doc_service.upload_document(
            file_stream=io.BytesIO(b"Existing corporate contract"),
            original_name="Contract.docx",
            user_id=1,
            repository_id=1
        )
        doc_id = doc['id']
        
        # 2. Share it in Group chat (conversation 102) as user 1
        with self.app.session_transaction() as sess:
            sess['user'] = {'user_id': 1, 'role': 'User', 'username': 'user1'}
            
        payload = {
            'resource_type': 'DOCUMENT',
            'document_id': doc_id
        }
        response = self.app.post('/api/v1/communication/conversations/102/share-resource', json=payload)
        self.assertEqual(response.status_code, 201)
        
        # Verify references exist
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM chat_file_reference WHERE document_id = ?", (doc_id,))
            cfr = cursor.fetchone()
            self.assertIsNotNone(cfr)
            self.assertEqual(cfr['conversation_id'], 102)
            self.assertEqual(cfr['sender_id'], 1)
        finally:
            conn.close()

    def test_03_chat_files_search_and_filtering(self):
        """Verify searching, sorting, and filtering operations on Chat Files endpoint."""
        # Upload a few files
        with self.app.session_transaction() as sess:
            sess['user'] = {'user_id': 1, 'role': 'User', 'username': 'user1'}

        # File 1: pdf in direct chat
        self.app.post('/api/v1/communication/conversations/101/upload-to-edms', data={
            'file': (io.BytesIO(b"invoice bytes"), 'Invoice.pdf')
        })
        # File 2: png in group chat
        self.app.post('/api/v1/communication/conversations/102/upload-to-edms', data={
            'file': (io.BytesIO(b"logo bytes"), 'logo.png')
        })

        # Test workspace listing API
        response = self.app.get('/api/v1/documents/chatfiles/workspace')
        self.assertEqual(response.status_code, 200)
        res = response.get_json()
        self.assertTrue(res['success'])
        self.assertEqual(len(res['results']), 2)
        self.assertEqual(res['stats']['total_active_files'], 2)

        # Filter by channel=group
        response = self.app.get('/api/v1/documents/chatfiles/workspace?channel=group')
        res = response.get_json()
        self.assertEqual(len(res['results']), 1)
        self.assertEqual(res['results'][0]['original_name'], 'logo.png')

        # Filter by category=image
        response = self.app.get('/api/v1/documents/chatfiles/workspace?category=image')
        res = response.get_json()
        self.assertEqual(len(res['results']), 1)
        self.assertEqual(res['results'][0]['original_name'], 'logo.png')

        # Search query matching file name
        response = self.app.get('/api/v1/documents/chatfiles/workspace?q=Invoice')
        res = response.get_json()
        self.assertEqual(len(res['results']), 1)
        self.assertEqual(res['results'][0]['original_name'], 'Invoice.pdf')

    def test_04_download_and_preview_security_validation(self):
        """Verify that download and preview validation strictly enforces permissions."""
        # 1. Create a document in My Drive belonging to user 2
        doc = self.doc_service.upload_document(
            file_stream=io.BytesIO(b"Top Secret file"),
            original_name="Secret.txt",
            user_id=2,
            repository_id=1
        )
        doc_id = doc['id']

        # 2. User 1 tries to access it -> should be denied
        with app.test_request_context():
            from flask import session
            session['user'] = {'user_id': 1, 'role': 'User', 'username': 'user1'}
            self.assertFalse(has_document_access(doc_id, 1))

        # 3. Share the file in chat conversation 101 (which User 1 is a participant of)
        with self.app.session_transaction() as sess:
            sess['user'] = {'user_id': 2, 'role': 'User', 'username': 'user2'}
        self.app.post('/api/v1/communication/conversations/101/share-resource', json={
            'resource_type': 'DOCUMENT',
            'document_id': doc_id
        })

        # 4. User 1 tries to access it now -> should be allowed since they are a conversation participant
        with app.test_request_context():
            from flask import session
            session['user'] = {'user_id': 1, 'role': 'User', 'username': 'user1'}
            self.assertTrue(has_document_access(doc_id, 1))

        # 5. User 1 tries to access via API route -> should be successful
        response = self.app.get(f'/api/v1/documents/{doc_id}/preview-data')
        self.assertEqual(response.status_code, 200)

        # 6. Delete original file -> should restrict user 1 from accessing it
        self.doc_service.soft_delete_document(doc_id, user_id=2)
        with app.test_request_context():
            from flask import session
            session['user'] = {'user_id': 1, 'role': 'User', 'username': 'user1'}
            self.assertFalse(has_document_access(doc_id, 1))

        # 7. Accessing API route should now be forbidden
        response = self.app.get(f'/api/v1/documents/{doc_id}/preview-data')
        self.assertEqual(response.status_code, 403)

if __name__ == "__main__":
    unittest.main()
