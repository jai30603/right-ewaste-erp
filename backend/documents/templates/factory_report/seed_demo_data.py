import sqlite3
import datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[4] / "database" / "erp.db"


def seed_demo_factory_data(report_date=None):
    if not report_date:
        report_date = datetime.date.today().isoformat()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print(f"Seeding demo purchase and sales data for date: {report_date}")

    # 1. Ensure Parties Exist
    parties = [
        ("P-SUP-001", "EcoRecycle India Pvt Ltd", "SUPPLIER", "27AAAAA0000A1Z5", "9876543210", "Mumbai Industrial Estate", "Mumbai", "Maharashtra", "27"),
        ("P-SUP-002", "GreenTech E-Waste Suppliers", "SUPPLIER", "27BBBBB1111B1Z6", "9876543211", "Andheri West, Mumbai", "Mumbai", "Maharashtra", "27"),
        ("P-SUP-003", "National E-Waste Collectors", "SUPPLIER", "27CCCCC2222C1Z7", "9876543212", "Thane West, Thane", "Thane", "Maharashtra", "27"),
        ("P-BUY-001", "Apex Metals & Alloys Pvt Ltd", "CUSTOMER", "27DDDDD3333D1Z8", "9876543213", "Kurla West, Mumbai", "Mumbai", "Maharashtra", "27"),
        ("P-BUY-002", "Sunlight Recyclers Pvt Ltd", "CUSTOMER", "27EEEEE4444E1Z9", "9876543214", "Navi Mumbai, Thane", "Thane", "Maharashtra", "27")
    ]

    party_ids = {}
    for code, name, ptype, gstin, phone, addr, city, state, state_code in parties:
        cursor.execute("SELECT id FROM party WHERE party_code = ?", (code,))
        row = cursor.fetchone()
        if row:
            party_ids[code] = row[0]
        else:
            cursor.execute("""
                INSERT INTO party (party_code, company_name, party_type, gstin, phone, billing_address, city, state, state_code)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (code, name, ptype, gstin, phone, addr, city, state, state_code))
            party_ids[code] = cursor.lastrowid

    # 2. Ensure Master Materials Exist (matching template names)
    materials = [
        ("MAT-CPU-01", "CPU", "BOTH", 50.0),
        ("MAT-KBD-01", "Keyboard", "BOTH", 20.0),
        ("MAT-LAP-01", "Laptop", "BOTH", 200.0),
        ("MAT-MON-01", "Lcd monitor", "BOTH", 20.0),
        ("MAT-PRN-01", "Printer/ Scanner", "BOTH", 200.0),
        ("MAT-FAN-01", "Table Fan", "BOTH", 15.0),
        ("MAT-BAT-01", "Battery lead acid water", "BOTH", 75.0),
        ("MAT-WOOD-01", "Wood / ply wood / palete", "BOTH", 10.0),
        ("MAT-FOAM-01", "Thermocole /foam", "BOTH", 5.0),
        ("MAT-SCR-01", "E-Waste scrap mixed", "BOTH", 15.0),
        ("MAT-COP-01", "Copper scraps", "BOTH", 600.0),
        ("MAT-ALU-01", "Aluminium scraps", "BOTH", 151.0),
        ("MAT-CBL-01", "Cable mixed", "BOTH", 80.0),
        ("MAT-PLS-01", "Plastic scraps", "BOTH", 35.0),
        ("MAT-PCB-01", "PCB scraps", "BOTH", 100.0)
    ]

    material_ids = {}
    for code, name, ttype, rate in materials:
        cursor.execute("SELECT id FROM material WHERE material_code = ?", (code,))
        row = cursor.fetchone()
        if row:
            material_ids[name] = row[0]
        else:
            cursor.execute("""
                INSERT INTO material (material_code, material_name, tracking_type, hsn_code, uom, gst_percentage)
                VALUES (?, ?, ?, '8549', 'KGS', 18.0)
            """, (code, name, ttype))
            material_ids[name] = cursor.lastrowid

    # 3. Seed 5 Sample Purchase Invoices
    purchases = [
        (party_ids["P-SUP-001"], [("CPU", 10, 50.0), ("Keyboard", 25, 20.0)]),
        (party_ids["P-SUP-002"], [("Laptop", 5, 200.0), ("Lcd monitor", 12, 20.0)]),
        (party_ids["P-SUP-003"], [("Printer/ Scanner", 8, 200.0), ("Table Fan", 15, 15.0)]),
        (party_ids["P-SUP-001"], [("Battery lead acid water", 50, 75.0), ("Wood / ply wood / palete", 100, 10.0)]),
        (party_ids["P-SUP-002"], [("E-Waste scrap mixed", 150, 15.0), ("Copper scraps", 40, 600.0), ("Aluminium scraps", 60, 151.0)])
    ]

    for idx, (sup_id, items) in enumerate(purchases, 1):
        pinv_num = f"PUR-{report_date.replace('-', '')}-{idx:03d}"
        subtotal = sum(q * r for _, q, r in items)

        cursor.execute("SELECT id FROM purchase_invoice WHERE purchase_invoice_number = ?", (pinv_num,))
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO purchase_invoice (
                    purchase_invoice_number, invoice_date, supplier_id, subtotal, grand_total, status, created_by
                ) VALUES (?, ?, ?, ?, ?, 'CONFIRMED', 'Admin')
            """, (pinv_num, report_date, sup_id, subtotal, subtotal * 1.18))
            purch_id = cursor.lastrowid

            for mat_name, qty, rate in items:
                mat_id = material_ids[mat_name]
                cursor.execute("""
                    INSERT INTO purchase_invoice_item (
                        purchase_invoice_id, material_id, quantity, weight, rate, amount
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (purch_id, mat_id, qty, qty, rate, qty * rate))

    # 4. Seed 5 Sample Sales Invoices
    sales = [
        (party_ids["P-BUY-001"], [("Copper scraps", 20, 600.0), ("Aluminium scraps", 30, 151.0)]),
        (party_ids["P-BUY-002"], [("Cable mixed", 45, 80.0), ("Plastic scraps", 75, 35.0)]),
        (party_ids["P-BUY-001"], [("PCB scraps", 25, 100.0), ("Thermocole /foam", 30, 5.0)]),
        (party_ids["P-BUY-002"], [("CPU", 4, 60.0), ("Laptop", 2, 220.0)]),
        (party_ids["P-BUY-001"], [("Printer/ Scanner", 3, 210.0), ("Keyboard", 10, 25.0)])
    ]

    for idx, (buy_id, items) in enumerate(sales, 1):
        sinv_num = f"SAL-{report_date.replace('-', '')}-{idx:03d}"
        subtotal = sum(q * r for _, q, r in items)

        cursor.execute("SELECT id FROM sales_invoice WHERE invoice_number = ?", (sinv_num,))
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO sales_invoice (
                    invoice_number, invoice_date, party_id, subtotal, grand_total, status
                ) VALUES (?, ?, ?, ?, ?, 'CONFIRMED')
            """, (sinv_num, report_date, buy_id, subtotal, subtotal * 1.18))
            sales_id = cursor.lastrowid

            for mat_name, qty, rate in items:
                mat_id = material_ids[mat_name]
                cursor.execute("""
                    INSERT INTO sales_invoice_item (
                        sales_invoice_id, material_id, quantity, weight, rate, amount
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (sales_id, mat_id, qty, qty, rate, qty * rate))

    conn.commit()
    conn.close()
    print("5 sample purchase invoices and 5 sample sales invoices successfully seeded!")


if __name__ == "__main__":
    seed_demo_factory_data()
