import unittest
import json
from backend.app import app
from backend.database import get_connection

class CommunicationModuleTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM notifications")
            cursor.execute("DELETE FROM message_receipts")
            cursor.execute("DELETE FROM message_reactions")
            cursor.execute("DELETE FROM messages")
            cursor.execute("DELETE FROM conversation_participants")
            cursor.execute("DELETE FROM conversations")
            cursor.execute("DELETE FROM users WHERE id IN (992, 993)")
            cursor.execute("""
                INSERT INTO users (id, username, full_name, email, department, designation, status, password_hash, erp_role)
                VALUES (992, 'rahul_test', 'Rahul Kumar', 'rahul@example.com', 'Purchase', 'Manager', 'ACTIVE', 'hash123', 'ADMIN')
            """)
            cursor.execute("""
                INSERT INTO users (id, username, full_name, email, department, designation, status, password_hash, erp_role)
                VALUES (993, 'priya_test', 'Priya Sharma', 'priya@example.com', 'Sales', 'Executive', 'ACTIVE', 'hash123', 'ADMIN')
            """)
            conn.commit()
        finally:
            conn.close()

    def test_communication_page_load(self):
        response = self.client.get("/communication")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Communication Platform", response.data)

    def test_user_discovery(self):
        response = self.client.get("/api/v1/communication/users")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertGreaterEqual(len(data["users"]), 2)

    def test_start_and_get_conversation(self):
        # Start conversation with user 992
        res = self.client.post(
            "/api/v1/communication/conversations",
            data=json.dumps({"other_user_id": 992}),
            content_type="application/json"
        )
        self.assertIn(res.status_code, (200, 201))
        conv_data = res.get_json()
        self.assertTrue(conv_data["success"])
        conv_id = conv_data["conversation_id"]

        # Fetch conversation list
        res_list = self.client.get("/api/v1/communication/conversations")
        self.assertEqual(res_list.status_code, 200)
        data_list = res_list.get_json()
        self.assertTrue(data_list["success"])
        found = any(c["id"] == conv_id for c in data_list["conversations"])
        self.assertTrue(found)

    def test_send_get_edit_delete_message(self):
        # Start conversation with user 993
        res = self.client.post(
            "/api/v1/communication/conversations",
            data=json.dumps({"other_user_id": 993}),
            content_type="application/json"
        )
        conv_id = res.get_json()["conversation_id"]

        # Send message
        send_res = self.client.post(
            f"/api/v1/communication/conversations/{conv_id}/messages",
            data=json.dumps({"content": "Hello Priya, please check invoice"}),
            content_type="application/json"
        )
        self.assertEqual(send_res.status_code, 201)
        msg_id = send_res.get_json()["message"]["id"]

        # Fetch messages
        get_res = self.client.get(f"/api/v1/communication/conversations/{conv_id}/messages")
        self.assertEqual(get_res.status_code, 200)
        msgs = get_res.get_json()["messages"]
        self.assertEqual(len(msgs), 1)
        self.assertIn("Hello Priya", msgs[0]["content"])

        # Edit message
        edit_res = self.client.put(
            f"/api/v1/communication/messages/{msg_id}",
            data=json.dumps({"content": "Hello Priya, updated invoice info"}),
            content_type="application/json"
        )
        self.assertEqual(edit_res.status_code, 200)

        # Soft delete message
        del_res = self.client.delete(f"/api/v1/communication/messages/{msg_id}")
        self.assertEqual(del_res.status_code, 200)

    def test_message_reactions(self):
        # Create conversation and send message
        res = self.client.post(
            "/api/v1/communication/conversations",
            data=json.dumps({"other_user_id": 992}),
            content_type="application/json"
        )
        conv_id = res.get_json()["conversation_id"]

        send_res = self.client.post(
            f"/api/v1/communication/conversations/{conv_id}/messages",
            data=json.dumps({"content": "Great work team!"}),
            content_type="application/json"
        )
        msg_id = send_res.get_json()["message"]["id"]

        # Add reaction
        rx_res = self.client.post(
            f"/api/v1/communication/messages/{msg_id}/reactions",
            data=json.dumps({"reaction": "👍"}),
            content_type="application/json"
        )
        self.assertEqual(rx_res.status_code, 200)

        # Remove reaction
        rx_del = self.client.delete(f"/api/v1/communication/messages/{msg_id}/reactions")
        self.assertEqual(rx_del.status_code, 200)

    def test_pin_and_search_conversations(self):
        # Create conversation
        res = self.client.post(
            "/api/v1/communication/conversations",
            data=json.dumps({"other_user_id": 992}),
            content_type="application/json"
        )
        conv_id = res.get_json()["conversation_id"]

        # Pin conversation
        pin_res = self.client.post(f"/api/v1/communication/conversations/{conv_id}/pin")
        self.assertEqual(pin_res.status_code, 200)

        # Unpin conversation
        unpin_res = self.client.post(f"/api/v1/communication/conversations/{conv_id}/unpin")
        self.assertEqual(unpin_res.status_code, 200)

        # Search messages
        search_res = self.client.get("/api/v1/communication/search?q=invoice")
        self.assertEqual(search_res.status_code, 200)
        self.assertTrue(search_res.get_json()["success"])

if __name__ == "__main__":
    unittest.main()
