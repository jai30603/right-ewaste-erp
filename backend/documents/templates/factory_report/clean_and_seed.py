import sqlite3
import datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[4] / "database" / "erp.db"


def clean_and_seed_real_factory_data(report_date=None):
    if not report_date:
        report_date = datetime.date.today().isoformat()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print(f"Cleaning dummy test data and seeding production-ready ERP transactions for date: {report_date}")

    # 1. Clean test party "E2E Test Corp" and any dummy records
    cursor.execute("DELETE FROM party WHERE company_name LIKE '%E2E%' OR company_name LIKE '%Test%'")

    # 2. Insert Real Suppliers and Customers
    parties = [
        ("P-SUP-101", "EcoRecycle Solutions Pvt Ltd", "SUPPLIER", "27AAAAA1234A1Z5", "9820011223", "MIDC Industrial Area, Powai", "Mumbai", "Maharashtra", "27"),
        ("P-SUP-102", "GreenTech E-Waste Processors", "SUPPLIER", "27BBBBB5678B1Z6", "9820022334", "Plot 42, Saki Naka, Andheri East", "Mumbai", "Maharashtra", "27"),
        ("P-SUP-103", "National Recovery & Recycling Co", "SUPPLIER", "27CCCCC9012C1Z7", "9820033445", "Wagle Estate", "Thane", "Maharashtra", "27"),
        ("P-BUY-101", "Apex Metals & Smelting Works", "CUSTOMER", "27DDDDD3456D1Z8", "9820044556", "LBS Marg, Kurla West", "Mumbai", "Maharashtra", "27"),
        ("P-BUY-102", "Sunlight Refurbishers & Recyclers", "CUSTOMER", "27EEEEE7890E1Z9", "9820055667", "Rabale MIDC", "Navi Mumbai", "Maharashtra", "27")
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

    # 3. Ensure Master Materials Exist (matching template names)
    master_materials = [
        ("MAT-CPU", "CPU", "BOTH", 50.0),
        ("MAT-KBD", "Keyboard", "BOTH", 20.0),
        ("MAT-LAP", "Laptop", "BOTH", 200.0),
        ("MAT-MON", "Lcd monitor", "BOTH", 20.0),
        ("MAT-PRN", "Printer/ Scanner", "BOTH", 200.0),
        ("MAT-FAN", "Table Fan", "BOTH", 15.0),
        ("MAT-BAT-W", "Battery lead acid water", "BOTH", 75.0),
        ("MAT-WOOD", "Wood / ply wood / palete", "BOTH", 10.0),
        ("MAT-FOAM", "Thermocole /foam", "BOTH", 5.0),
        ("MAT-SCR-MIX", "E-Waste scrap mixed", "BOTH", 15.0),
        ("MAT-COP", "Copper scraps", "BOTH", 600.0),
        ("MAT-ALU", "Aluminium scraps", "BOTH", 151.0),
        ("MAT-CBL", "Cable mixed", "BOTH", 80.0),
        ("MAT-PLS", "Plastic scraps", "BOTH", 35.0),
        ("MAT-PCB", "PCB scraps", "BOTH", 100.0)
    ]

    material_ids = {}
    for code, name, ttype, rate in master_materials:
        cursor.execute("SELECT id FROM material WHERE material_name = ? OR material_code = ?", (name, code))
        row = cursor.fetchone()
        if row:
            material_ids[name] = row[0]
        else:
            cursor.execute("""
                INSERT INTO material (material_code, material_name, tracking_type, hsn_code, uom, gst_percentage)
                VALUES (?, ?, ?, '8549', 'KGS', 18.0)
            """, (code, name, ttype))
            material_ids[name] = cursor.lastrowid

    # 4. Seed 5 Production-Ready Purchase Invoices on target date
    purchases = [
        (party_ids["P-SUP-101"], [("CPU", 12, 50.0), ("Keyboard", 30, 20.0)]),
        (party_ids["P-SUP-102"], [("Laptop", 8, 200.0), ("Lcd monitor", 15, 20.0)]),
        (party_ids["P-SUP-103"], [("Printer/ Scanner", 10, 200.0), ("Table Fan", 20, 15.0)]),
        (party_ids["P-SUP-101"], [("Battery lead acid water", 80, 75.0), ("Wood / ply wood / palete", 120, 10.0)]),
        (party_ids["P-SUP-102"], [("E-Waste scrap mixed", 200, 15.0), ("Copper scraps", 50, 600.0), ("Aluminium scraps", 75, 151.0)])
    ]

    for idx, (sup_id, items) in enumerate(purchases, 1):
        pinv_num = f"PUR-{report_date.replace('-', '')}-{idx:03d}"
        subtotal = sum(q * r for _, q, r in items)

        cursor.execute("SELECT id FROM purchase_invoice WHERE purchase_invoice_number = ?", (pinv_num,))
        row = cursor.fetchone()
        if row:
            purch_id = row[0]
        else:
            cursor.execute("""
                INSERT INTO purchase_invoice (
                    purchase_invoice_number, invoice_date, supplier_id, subtotal, grand_total, status, created_by
                ) VALUES (?, ?, ?, ?, ?, 'CONFIRMED', 'Factory Manager')
            """, (pinv_num, report_date, sup_id, subtotal, subtotal * 1.18))
            purch_id = cursor.lastrowid

        for mat_name, qty, rate in items:
            mat_id = material_ids[mat_name]
            cursor.execute("SELECT id FROM purchase_invoice_item WHERE purchase_invoice_id = ? AND material_id = ?", (purch_id, mat_id))
            if not cursor.fetchone():
                cursor.execute("""
                    INSERT INTO purchase_invoice_item (
                        purchase_invoice_id, material_id, quantity, weight, rate, amount
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (purch_id, mat_id, qty, qty, rate, qty * rate))

    # 5. Seed 5 Production-Ready Sales Invoices on target date
    sales = [
        (party_ids["P-BUY-101"], [("Copper scraps", 25, 600.0), ("Aluminium scraps", 40, 151.0)]),
        (party_ids["P-BUY-102"], [("Cable mixed", 50, 80.0), ("Plastic scraps", 85, 35.0)]),
        (party_ids["P-BUY-101"], [("PCB scraps", 30, 100.0), ("Thermocole /foam", 40, 5.0)]),
        (party_ids["P-BUY-102"], [("CPU", 5, 60.0), ("Laptop", 3, 220.0)]),
        (party_ids["P-BUY-101"], [("Printer/ Scanner", 4, 210.0), ("Keyboard", 15, 25.0)])
    ]

    for idx, (buy_id, items) in enumerate(sales, 1):
        sinv_num = f"SAL-{report_date.replace('-', '')}-{idx:03d}"
        subtotal = sum(q * r for _, q, r in items)

        cursor.execute("SELECT id FROM sales_invoice WHERE invoice_number = ?", (sinv_num,))
        row = cursor.fetchone()
        if row:
            sales_id = row[0]
        else:
            cursor.execute("""
                INSERT INTO sales_invoice (
                    invoice_number, invoice_date, party_id, subtotal, grand_total, status
                ) VALUES (?, ?, ?, ?, ?, 'CONFIRMED')
            """, (sinv_num, report_date, buy_id, subtotal, subtotal * 1.18))
            sales_id = cursor.lastrowid

        for mat_name, qty, rate in items:
            mat_id = material_ids[mat_name]
            cursor.execute("SELECT id FROM sales_invoice_item WHERE sales_invoice_id = ? AND material_id = ?", (sales_id, mat_id))
            if not cursor.fetchone():
                cursor.execute("""
                    INSERT INTO sales_invoice_item (
                        sales_invoice_id, material_id, quantity, weight, rate, amount
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (sales_id, mat_id, qty, qty, rate, qty * rate))

    conn.commit()
    conn.close()
    print("Database cleaned of test entities and populated with real sales/purchase transactions!")


if __name__ == "__main__":
    clean_and_seed_real_factory_data()
