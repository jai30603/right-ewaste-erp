import unittest
import json
from backend.app import app
from backend.database import get_connection

class CommunicationGroupsTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        conn = get_connection()
        try:
            cursor = conn.cursor()
            # Clean tables
            cursor.execute("DELETE FROM notifications")
            cursor.execute("DELETE FROM pinned_messages")
            cursor.execute("DELETE FROM mentions")
            cursor.execute("DELETE FROM message_reactions")
            cursor.execute("DELETE FROM message_receipts")
            cursor.execute("DELETE FROM messages")
            cursor.execute("DELETE FROM conversation_participants")
            cursor.execute("DELETE FROM conversations")
            # Seed test users with unique IDs to prevent conflict with existing data
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

    def test_default_groups_are_seeded(self):
        # Trigger DB initializer
        from backend.database import initialize_database
        initialize_database()
        
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM conversations WHERE type='GROUP'")
            count = cursor.fetchone()[0]
            self.assertGreaterEqual(count, 8)  # at least 8 default groups seeded
        finally:
            conn.close()

    def test_create_and_manage_group(self):
        # Create group
        payload = {
            "name": "Design Team",
            "description": "Graphics and UX collaboration",
            "member_ids": [992, 993]
        }
        res = self.client.post(
            "/api/v1/communication/groups",
            data=json.dumps(payload),
            content_type="application/json"
        )
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertTrue(data["success"])
        conv_id = data["conversation_id"]

        # Fetch group members
        res_mem = self.client.get(f"/api/v1/communication/groups/{conv_id}/members")
        self.assertEqual(res_mem.status_code, 200)
        members = res_mem.get_json()["members"]
        self.assertEqual(len(members), 3) # creator + 2 added members

        # Edit Group details
        edit_payload = {
            "name": "Design & UI Team",
            "description": "Visual UI Design discussions"
        }
        edit_res = self.client.put(
            f"/api/v1/communication/groups/{conv_id}",
            data=json.dumps(edit_payload),
            content_type="application/json"
        )
        self.assertEqual(edit_res.status_code, 200)

        # Archive group
        arch_res = self.client.post(f"/api/v1/communication/groups/{conv_id}/archive")
        self.assertEqual(arch_res.status_code, 200)

        # Confirm send message fails in archived group
        send_res = self.client.post(
            f"/api/v1/communication/conversations/{conv_id}/messages",
            data=json.dumps({"content": "Hello Team"}),
            content_type="application/json"
        )
        self.assertEqual(send_res.status_code, 403)

        # Restore group
        rest_res = self.client.post(f"/api/v1/communication/groups/{conv_id}/restore")
        self.assertEqual(rest_res.status_code, 200)

        # Add member to group
        add_res = self.client.post(
            f"/api/v1/communication/groups/{conv_id}/members",
            data=json.dumps({"user_id": 993}),
            content_type="application/json"
        )
        self.assertEqual(add_res.status_code, 200)

        # Remove member
        rem_res = self.client.delete(f"/api/v1/communication/groups/{conv_id}/members/993")
        self.assertEqual(rem_res.status_code, 200)

    def test_pinned_messages_and_seen_by(self):
        # Create group
        res = self.client.post(
            "/api/v1/communication/groups",
            data=json.dumps({"name": "Sales Group", "member_ids": [992]}),
            content_type="application/json"
        )
        conv_id = res.get_json()["conversation_id"]

        # Send group message
        send_res = self.client.post(
            f"/api/v1/communication/conversations/{conv_id}/messages",
            data=json.dumps({"content": "Please review company policy document"}),
            content_type="application/json"
        )
        msg_id = send_res.get_json()["message"]["id"]

        # Pin message
        pin_res = self.client.post(f"/api/v1/communication/conversations/{conv_id}/pin-message/{msg_id}")
        self.assertEqual(pin_res.status_code, 200)

        # Fetch pinned messages
        pinned_res = self.client.get(f"/api/v1/communication/conversations/{conv_id}/pinned-messages")
        self.assertEqual(pinned_res.status_code, 200)
        pinned = pinned_res.get_json()["pinned_messages"]
        self.assertEqual(len(pinned), 1)
        self.assertEqual(pinned[0]["message_id"], msg_id)

        # Unpin message
        unpin_res = self.client.delete(f"/api/v1/communication/conversations/{conv_id}/pin-message/{msg_id}")
        self.assertEqual(unpin_res.status_code, 200)

        # Get message seen by readers list
        seen_res = self.client.get(f"/api/v1/communication/messages/{msg_id}/seen")
        self.assertEqual(seen_res.status_code, 200)
        self.assertTrue(seen_res.get_json()["success"])

    def test_username_mentions_and_notifications(self):
        # Create group conversation
        res = self.client.post(
            "/api/v1/communication/groups",
            data=json.dumps({"name": "Test Group", "member_ids": [992]}),
            content_type="application/json"
        )
        conv_id = res.get_json()["conversation_id"]

        # Send message with a mention
        send_res = self.client.post(
            f"/api/v1/communication/conversations/{conv_id}/messages",
            data=json.dumps({"content": "Hello @rahul_test check this report"}),
            content_type="application/json"
        )
        self.assertEqual(send_res.status_code, 201)

        # Confirm notifications are sent (1 for Added to Group, 1 for New Mention)
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM notifications WHERE user_name = 'rahul_test'")
            self.assertEqual(cursor.fetchone()[0], 2)
            
            cursor.execute("SELECT title, message FROM notifications WHERE user_name = 'rahul_test' AND title = 'New Mention'")
            notif = cursor.fetchone()
            self.assertIsNotNone(notif)
            self.assertIn("mentioned you", notif[1])
        finally:
            conn.close()

if __name__ == "__main__":
    unittest.main()
