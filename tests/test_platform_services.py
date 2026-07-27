import unittest
import os
import sys
import json
from datetime import datetime

# Insert backend directory in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from database import get_connection
from erp_platform.events.event_bus import event_bus, ErpEvent
from erp_platform.audit.activity_center import log_activity, get_activities
from erp_platform.audit.audit_engine import audit_change, get_audit_trail
from erp_platform.notifications.notification_service import send_notification, get_notifications, mark_read, get_unread_count
from erp_platform.kpi.kpi_engine import compute_kpi, compute_all_kpis
from erp_platform.export.export_engine import format_for_display

class PlatformServicesTest(unittest.TestCase):
    def setUp(self):
        self.conn = get_connection()
        # Clean up any potential test records from tests
        self.conn.execute("DELETE FROM platform_event_log WHERE event_type LIKE 'test.%'")
        self.conn.execute("DELETE FROM activity_log WHERE action LIKE 'Test Action%'")
        self.conn.execute("DELETE FROM audit_log WHERE entity_type = 'test_table'")
        self.conn.execute("DELETE FROM notifications WHERE user_name = 'test_notif_user'")
        self.conn.commit()

    def tearDown(self):
        self.conn.execute("DELETE FROM platform_event_log WHERE event_type LIKE 'test.%'")
        self.conn.execute("DELETE FROM activity_log WHERE action LIKE 'Test Action%'")
        self.conn.execute("DELETE FROM audit_log WHERE entity_type = 'test_table'")
        self.conn.execute("DELETE FROM notifications WHERE user_name = 'test_notif_user'")
        self.conn.commit()
        self.conn.close()

    def test_event_bus(self):
        event_received = []

        def test_handler(event):
            event_received.append(event)

        event_bus.subscribe("test.event", test_handler)
        
        event = ErpEvent(
            event_type="test.event",
            source_module="test_module",
            payload={"key": "value"},
            user_name="test_user"
        )
        
        event_bus.publish(event, async_mode=False)
        
        self.assertEqual(len(event_received), 1)
        self.assertEqual(event_received[0].event_type, "test.event")
        self.assertEqual(event_received[0].payload["key"], "value")

        # Verify DB persistence
        cursor = self.conn.execute("SELECT * FROM platform_event_log WHERE event_type = 'test.event'")
        row = cursor.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row['source_module'], 'test_module')
        payload = json.loads(row['payload'])
        self.assertEqual(payload['key'], 'value')

    def test_activity_center(self):
        log_activity(
            action="Test Action logged",
            module="test_module",
            details="Some detailed info",
            severity="WARNING",
            user_name="test_user",
            conn=self.conn
        )
        self.conn.commit()

        activities = get_activities(limit=5, module="test_module")
        self.assertTrue(len(activities) >= 1)
        self.assertEqual(activities[0]['action'], "Test Action logged")
        self.assertEqual(activities[0]['severity'], "WARNING")
        self.assertEqual(activities[0]['user_name'], "test_user")

    def test_audit_engine(self):
        old_val = {"status": "DRAFT", "amount": 100}
        new_val = {"status": "SUBMITTED", "amount": 120}
        
        audit_change(
            table_name="test_table",
            record_id=42,
            action="UPDATE",
            old_values=old_val,
            new_values=new_val,
            changed_by="test_auditor",
            reason="UAT testing",
            session_id="sess_12345",
            ip_address="127.0.0.1",
            conn=self.conn
        )
        self.conn.commit()

        trail = get_audit_trail(table_name="test_table", record_id=42)
        self.assertEqual(len(trail), 1)
        self.assertEqual(trail[0]['changed_by'], "test_auditor")
        self.assertEqual(trail[0]['action'], "UPDATE")
        self.assertEqual(trail[0]['ip_address'], "127.0.0.1")
        self.assertEqual(trail[0]['session_id'], "sess_12345")
        
        # Verify old/new values are restored from JSON details
        restored_old = json.loads(trail[0]['old_values'])
        restored_new = json.loads(trail[0]['new_values'])
        self.assertEqual(restored_old['status'], "DRAFT")
        self.assertEqual(restored_new['amount'], 120)

    def test_notification_service(self):
        send_notification(
            user_name="test_notif_user",
            title="Test Title",
            message="Test Message Content",
            notification_type="SUCCESS",
            related_module="test_module",
            related_id="101",
            conn=self.conn
        )
        self.conn.commit()

        unread = get_unread_count("test_notif_user")
        self.assertEqual(unread, 1)

        notifs = get_notifications("test_notif_user")
        self.assertEqual(len(notifs), 1)
        self.assertEqual(notifs[0]['title'], "Test Title")
        self.assertEqual(notifs[0]['notification_type'], "SUCCESS")

        mark_read(notification_id=notifs[0]['id'])
        unread = get_unread_count("test_notif_user")
        self.assertEqual(unread, 0)

    def test_kpi_engine(self):
        # We should at least be able to compute all seeded KPIs without database exception
        kpis = compute_all_kpis()
        self.assertTrue(len(kpis) > 0)
        
        # Let's test a single key
        res = compute_kpi("pending_certificates")
        self.assertEqual(res['kpi_key'], "pending_certificates")
        self.assertTrue('value' in res)

    def test_export_engine(self):
        dummy_data = [
            {"name": "Alice", "role": "Admin"},
            {"name": "Bob", "role": "User"}
        ]
        res = format_for_display(dummy_data, columns=["name"])
        self.assertEqual(res['count'], 2)
        self.assertEqual(res['columns'], ["name"])
        self.assertEqual(res['rows'][0]["name"], "Alice")
