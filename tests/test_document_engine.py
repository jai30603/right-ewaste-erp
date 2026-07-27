import sys
import os
import unittest
from pathlib import Path

# Add backend to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database import get_connection
from document_engine.cache import render_cache
from document_engine.parsers.data_parser import parse_clipboard_table, parse_csv_file
from document_engine.placeholders.placeholder_resolver import resolve_placeholders
from document_engine.repositories.document_repository import insert_audit_log, get_audit_logs
from document_engine.repositories import template_repository
from document_engine.services.document_service import render_document

class DocumentEngineTest(unittest.TestCase):
    
    def test_placeholder_resolution(self):
        context = {
            "company": {
                "company_name": "Test Company Ltd",
                "city": "Mumbai"
            },
            "party": {
                "company_name": "Supplier Corp",
                "billing_address": "456 Supplier St"
            },
            "purchase": {
                "purchase_invoice_number": "PUR-2026-000001",
                "invoice_date": "2026-07-17"
            },
            "document": {
                "certificate_number": "CERT-2026-000001",
                "declaration_text": "Responsibly certified e-waste yields."
            }
        }
        
        # Test basic text resolution
        text = "This is to certify that {{SUPPLIER_NAME}} at {{SUPPLIER_ADDRESS}} delivered waste on {{PURCHASE_DATE}}."
        resolved = resolve_placeholders(text, context)
        self.assertEqual(resolved, "This is to certify that Supplier Corp at 456 Supplier St delivered waste on 2026-07-17.")
        
        # Test company placeholder
        text_company = "Certified by {{COMPANY_NAME}}."
        resolved_company = resolve_placeholders(text_company, context)
        self.assertEqual(resolved_company, "Certified by Test Company Ltd.")

    def test_clipboard_tsv_parsing(self):
        # Clipboard data represented as TSV text
        raw_clipboard = "Material Name\tQty\tWeight\r\nBattery scrap\t10 Pcs\t100 KG\r\nPlastic waste\t20 Pcs\t200 KG\r\n"
        rows = parse_clipboard_table(raw_clipboard)
        
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0], ["Material Name", "Qty", "Weight"])
        self.assertEqual(rows[1], ["Battery scrap", "10 Pcs", "100 KG"])
        self.assertEqual(rows[2], ["Plastic waste", "20 Pcs", "200 KG"])

    def test_transient_render_cache(self):
        # Generate cache key
        key1 = render_cache.generate_key("STANDARD", 1, 42, "{}", "[]")
        key2 = render_cache.generate_key("STANDARD", 1, 42, "{}", "[]")
        key3 = render_cache.generate_key("STANDARD", 1, 43, "{}", "[]")
        
        self.assertEqual(key1, key2)
        self.assertNotEqual(key1, key3)
        
        # Set and get cache bytes
        mock_pdf_bytes = b"%PDF-1.4 Mock Bytes"
        render_cache.set_cache(key1, mock_pdf_bytes)
        
        cached = render_cache.get(key1)
        self.assertEqual(cached, mock_pdf_bytes)
        
        # Test clear
        render_cache.clear()
        self.assertIsNone(render_cache.get(key1))

    def test_unified_audit_logging(self):
        conn = get_connection()
        try:
            # Insert log
            log_id = insert_audit_log(
                user_name="test_user",
                action="TEMPLATE_CREATED",
                entity_type="template",
                entity_id="STANDARD",
                new_version=2,
                details="Updated company standard template wording",
                conn=conn
            )
            self.assertIsNotNone(log_id)
            conn.commit()  # Commit transaction so that other connections can see it
            
            # Fetch log
            logs = get_audit_logs(entity_type="template", entity_id="STANDARD", limit=1)
            self.assertTrue(len(logs) > 0)
            self.assertEqual(logs[0]["user_name"], "test_user")
            self.assertEqual(logs[0]["action"], "TEMPLATE_CREATED")
            self.assertEqual(logs[0]["new_version"], 2)
            
        finally:
            # Clean up test row
            cursor = conn.cursor()
            cursor.execute("DELETE FROM audit_log WHERE user_name = 'test_user'")
            conn.commit()
            conn.close()

    def test_template_versioning(self):
        # Retrieve latest template versions
        templates = template_repository.get_templates_list()
        self.assertTrue(len(templates) > 0)
        
        # Save a new version for a test template
        test_key = "UNIT_TEST_TPL"
        t_data = {
            "template_key": test_key,
            "template_name": "Unit Test Template Layout",
            "title": "TEST TITLE",
            "declaration_text": "Sample declaration.",
            "version": 1,
            "template_json": '{"layout": "A4_PORTRAIT", "elements": []}'
        }
        
        conn = get_connection()
        conn.execute("PRAGMA foreign_keys = OFF")  # Disable FK checks to avoid OperationalError on cleanup
        cursor = conn.cursor()
        try:
            # Save first version
            ver1 = template_repository.save_template_version(t_data)
            
            # Save second version
            ver2 = template_repository.save_template_version(t_data)
            
            self.assertEqual(ver2, ver1 + 1)
            
            # Load latest version
            latest = template_repository.get_template_by_key(test_key)
            self.assertEqual(latest["version"], ver2)
            
        finally:
            cursor.execute("DELETE FROM document_template WHERE template_key = ?", (test_key,))
            conn.commit()
            conn.close()

if __name__ == "__main__":
    unittest.main()
