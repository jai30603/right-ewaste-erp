import sqlite3
import random
import sys
from pathlib import Path
from datetime import date, timedelta

# Set up paths so we can import services
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "backend"))
sys.path.insert(0, str(BASE_DIR))

# Import calculate_gst
from services.invoice_service import calculate_gst

def get_db_connection():
    conn = sqlite3.connect("database/erp.db")
    conn.row_factory = sqlite3.Row
    return conn

def populate():
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Clean existing invoices and invoice items
    print("Cleaning transactions...")
    cursor.execute("DELETE FROM sales_invoice_item")
    cursor.execute("DELETE FROM sales_invoice")
    cursor.execute("DELETE FROM purchase_invoice_item")
    cursor.execute("DELETE FROM purchase_invoice")
    conn.commit()

    # 2. Add some standard materials if they don't exist
    materials_to_add = [
        {"code": "MAT-00010", "name": "Motherboard Grade-A", "hsn": "8548", "uom": "KG", "gst": 18.0, "category": "E-waste", "desc": "High quality motherboard scrap"},
        {"code": "MAT-00011", "name": "Copper Wire Scrap", "hsn": "7404", "uom": "KGS", "gst": 18.0, "category": "Metal", "desc": "Clean copper wire scrap"},
        {"code": "MAT-00012", "name": "Li-ion Battery Scrap", "hsn": "8548", "uom": "KGS", "gst": 18.0, "category": "Battery", "desc": "Lithium-ion battery scrap"},
        {"code": "MAT-00013", "name": "Aluminium Heat Sinks", "hsn": "7602", "uom": "KG", "gst": 12.0, "category": "Metal", "desc": "Aluminium heat sink scrap"},
        {"code": "MAT-00014", "name": "Plastic Outer Shells", "hsn": "3915", "uom": "KG", "gst": 18.0, "category": "Plastic", "desc": "Mixed plastic scrap"},
        {"code": "MAT-00015", "name": "RAM Sticks Mixed", "hsn": "8548", "uom": "KG", "gst": 18.0, "category": "E-waste", "desc": "Mixed computer RAM sticks"},
        {"code": "MAT-00016", "name": "Power Supply Unit (PSU)", "hsn": "8504", "uom": "PCS", "gst": 18.0, "category": "E-waste", "desc": "Computer SMPS / PSU scrap"},
        {"code": "MAT-00017", "name": "Hard Disk Drive (HDD)", "hsn": "8471", "uom": "PCS", "gst": 18.0, "category": "E-waste", "desc": "Computer hard drives for recycling"},
        {"code": "MAT-00018", "name": "Mixed Cables & Wires", "hsn": "8544", "uom": "KGS", "gst": 18.0, "category": "Cables", "desc": "PVC insulated copper cables"},
        {"code": "MAT-00019", "name": "Keyboards & Mice Scrap", "hsn": "8471", "uom": "KGS", "gst": 12.0, "category": "Plastic", "desc": "Input devices plastic scrap"},
    ]

    for m in materials_to_add:
        cursor.execute("SELECT id FROM material WHERE material_code = ?", (m["code"],))
        row = cursor.fetchone()
        if not row:
            cursor.execute("""
                INSERT INTO material (material_code, material_name, hsn_code, uom, gst_percentage, category, description, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            """, (m["code"], m["name"], m["hsn"], m["uom"], m["gst"], m["category"], m["desc"]))
    conn.commit()

    # Get active material list
    cursor.execute("SELECT * FROM material WHERE is_active = 1")
    materials = [dict(r) for r in cursor.fetchall()]
    print(f"Loaded {len(materials)} materials.")

    # 3. Add some standard parties if they don't exist
    parties_to_add = [
        {"code": "PTY-00010", "name": "Apex E-Recyclers", "type": "CUSTOMER", "gst": "27APXER1234A1Z1", "state": "Maharashtra", "state_code": "27"},
        {"code": "PTY-00011", "name": "Nova Scrap Traders", "type": "SUPPLIER", "gst": "27NOVAS4321B1Z2", "state": "Maharashtra", "state_code": "27"},
        {"code": "PTY-00012", "name": "Gujarat E-Waste Care", "type": "CUSTOMER", "gst": "24GUJEW5555C1Z3", "state": "Gujarat", "state_code": "24"},
        {"code": "PTY-00013", "name": "Delhi Green Recovery", "type": "SUPPLIER", "gst": "07DELGR9999D1Z4", "state": "Delhi", "state_code": "07"},
        {"code": "PTY-00014", "name": "Matrix Recycling Corp", "type": "BOTH", "gst": "27MATRX8888E1Z5", "state": "Maharashtra", "state_code": "27"},
        {"code": "PTY-00015", "name": "Karnataka Metal Solutions", "type": "SUPPLIER", "gst": "29KARME7777F1Z6", "state": "Karnataka", "state_code": "29"},
        {"code": "PTY-00016", "name": "Zenith Computers Scrap", "type": "CUSTOMER", "gst": "27ZENIT1111G1Z7", "state": "Maharashtra", "state_code": "27"},
        {"code": "PTY-00017", "name": "Mumbai Scrap House", "type": "BOTH", "gst": None, "state": "Maharashtra", "state_code": "27"},
        {"code": "PTY-00018", "name": "Alpha Tech Traders", "type": "CUSTOMER", "gst": "07ALPHT2222H1Z8", "state": "Delhi", "state_code": "07"},
        {"code": "PTY-00019", "name": "Vanguard Eco Systems", "type": "SUPPLIER", "gst": "24VANGE3333J1Z9", "state": "Gujarat", "state_code": "24"},
    ]

    for p in parties_to_add:
        cursor.execute("SELECT id FROM party WHERE party_code = ?", (p["code"],))
        row = cursor.fetchone()
        if not row:
            cursor.execute("""
                INSERT INTO party (
                    party_code, company_name, party_type, gstin, state, state_code,
                    billing_address, shipping_address, phone, city, pincode, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """, (
                p["code"], p["name"], p["type"], p["gst"], p["state"], p["state_code"],
                p["state"] + " Office", p["state"] + " Yard", "9876543210", "Mumbai", "400001"
            ))
    conn.commit()

    # Get active parties
    cursor.execute("SELECT * FROM party WHERE is_active = 1")
    parties = [dict(r) for r in cursor.fetchall()]
    customers = [p for p in parties if p["party_type"] in ("CUSTOMER", "BOTH")]
    suppliers = [p for p in parties if p["party_type"] in ("SUPPLIER", "BOTH")]
    print(f"Loaded {len(parties)} parties. Customers: {len(customers)}, Suppliers: {len(suppliers)}")

    # 4. Generate 50 Purchase Invoices and 50 Sales Invoices
    # Distribute dates over 2024, 2025, and 2026.
    # We will generate about 30 monthly slots. In each slot:
    # - 1 or 2 purchases
    # - 1 or 2 sales
    start_date = date(2024, 1, 1)
    end_date = date(2026, 7, 1)
    
    total_slots = 30
    delta_days = (end_date - start_date).days
    
    payment_modes = ["Cash", "NEFT", "RTGS", "UPI", "Cheque", "Credit"]
    transporters = ["Express Cargo", "Blue Dart", "V-Trans", "SafeExpress", "Local Tempo", "Self Picked"]
    vehicle_prefixes = ["MH-04-GP-", "MH-43-AQ-", "GJ-01-XX-", "DL-01-YY-", "KA-03-ZZ-"]

    sales_count = 0
    purchase_count = 0

    print("Generating mock transactions...")

    # We want around 50 of each, let's create exactly 50 Sales and 50 Purchase
    for i in range(50):
        # Determine date spread out
        days_offset = int((delta_days / 50) * i) + random.randint(-5, 5)
        days_offset = max(0, min(delta_days, days_offset))
        inv_date = (start_date + timedelta(days=days_offset)).isoformat()

        # ─── A. Sales Invoice ───
        sales_count += 1
        sales_number = f"INV-SL-{sales_count:05d}"
        cust = random.choice(customers)
        pay_mode = random.choice(payment_modes)
        trans = random.choice(transporters)
        veh = random.choice(vehicle_prefixes) + f"{random.randint(1000, 9999)}"
        
        # Pick 1-3 items
        items_count = random.randint(1, 3)
        selected_materials = random.sample(materials, items_count)
        
        items_list = []
        subtotal = 0.0
        for mat in selected_materials:
            qty = round(random.uniform(10.0, 300.0), 2)
            # Make sure sales rate is slightly higher than standard material rate (which is averaging around 100)
            rate = round(random.uniform(60.0, 1800.0), 2)
            amount = round(qty * rate, 2)
            subtotal += amount
            items_list.append({
                "material_id": mat["id"],
                "quantity": qty,
                "rate": rate,
                "amount": amount,
                "gst_percentage": mat["gst_percentage"]
            })

        # Calculate GST matching company state (27)
        tax_calc = calculate_gst(subtotal, items_list, "27", cust["state_code"])
        
        cursor.execute("""
            INSERT INTO sales_invoice (
                invoice_number, invoice_date, party_id, payment_mode, transporter, vehicle_number, remarks,
                subtotal, cgst, sgst, igst, round_off, grand_total, status, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'CONFIRMED', 1)
        """, (
            sales_number, inv_date, cust["id"], pay_mode, trans, veh, "Mock Sales Invoice",
            subtotal, tax_calc["cgst"], tax_calc["sgst"], tax_calc["igst"],
            tax_calc["round_off"], tax_calc["grand_total"]
        ))
        sales_invoice_id = cursor.lastrowid

        for it in items_list:
            cursor.execute("""
                INSERT INTO sales_invoice_item (
                    sales_invoice_id, material_id, quantity, rate, amount
                ) VALUES (?, ?, ?, ?, ?)
            """, (sales_invoice_id, it["material_id"], it["quantity"], it["rate"], it["amount"]))


        # ─── B. Purchase Invoice ───
        purchase_count += 1
        pur_number = f"PUR-PI-{purchase_count:05d}"
        supp = random.choice(suppliers)
        pay_mode = random.choice(payment_modes)
        trans = random.choice(transporters)
        veh = random.choice(vehicle_prefixes) + f"{random.randint(1000, 9999)}"
        supp_inv_num = f"SUPP-{(10000 + purchase_count)}"

        # Pick 1-3 items
        items_count = random.randint(1, 3)
        selected_materials = random.sample(materials, items_count)
        
        items_list = []
        subtotal = 0.0
        for mat in selected_materials:
            qty = round(random.uniform(50.0, 500.0), 2)
            # Purchase rate slightly lower than sales
            rate = round(random.uniform(40.0, 1200.0), 2)
            amount = round(qty * rate, 2)
            subtotal += amount
            items_list.append({
                "material_id": mat["id"],
                "quantity": qty,
                "rate": rate,
                "amount": amount,
                "gst_percentage": mat["gst_percentage"]
            })

        # Calculate GST matching company state (27)
        tax_calc = calculate_gst(subtotal, items_list, "27", supp["state_code"])

        cursor.execute("""
            INSERT INTO purchase_invoice (
                purchase_invoice_number, invoice_date, supplier_id, supplier_invoice_number, payment_mode, transporter, vehicle_number, remarks,
                subtotal, cgst, sgst, igst, gst_amount, round_off, grand_total, status, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'CONFIRMED', 1)
        """, (
            pur_number, inv_date, supp["id"], supp_inv_num, pay_mode, trans, veh, "Mock Purchase Invoice",
            subtotal, tax_calc["cgst"], tax_calc["sgst"], tax_calc["igst"],
            tax_calc["cgst"] + tax_calc["sgst"] + tax_calc["igst"],
            tax_calc["round_off"], tax_calc["grand_total"]
        ))
        purchase_invoice_id = cursor.lastrowid

        for it in items_list:
            cursor.execute("""
                INSERT INTO purchase_invoice_item (
                    purchase_invoice_id, material_id, quantity, rate, amount
                ) VALUES (?, ?, ?, ?, ?)
            """, (purchase_invoice_id, it["material_id"], it["quantity"], it["rate"], it["amount"]))

    conn.commit()
    conn.close()
    print(f"Successfully generated {sales_count} Sales Invoices and {purchase_count} Purchase Invoices spanning 2024 to 2026!")

if __name__ == "__main__":
    populate()
