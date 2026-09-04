import sqlite3
import json
import datetime
from database import get_connection

def _row_to_dict(cursor, row):
    if not row:
        return None
    try:
        if hasattr(row, "keys"):
            return dict(row)
    except Exception:
        pass
    desc = [d[0] for d in cursor.description]
    return dict(zip(desc, row))


def get_erp_data_for_report(report_date, conn=None):
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        cursor = conn.cursor()

        # 1. Company Information
        company_info = {
            "company_name": "Right Ewaste Recycle Private Limited",
            "branch_location": "Mumbai Branch HQ",
            "registration_no": "E-WASTE-REG-2026"
        }
        try:
            cursor.execute("SELECT * FROM company LIMIT 1")
            row = cursor.fetchone()
            if row:
                c_dict = _row_to_dict(cursor, row)
                if c_dict.get("company_name"):
                    company_info["company_name"] = c_dict["company_name"]
                addr_parts = [c_dict.get("address_line_1"), c_dict.get("address_line_2"), c_dict.get("city"), c_dict.get("state"), c_dict.get("pincode")]
                addr_str = ", ".join([p for p in addr_parts if p])
                if addr_str:
                    company_info["branch_location"] = addr_str
        except Exception:
            pass

        # 2. Employee Attendance Summary on Date
        cursor.execute("SELECT COUNT(*) FROM employee_attendance WHERE attendance_date = ? AND attendance_status = 'Present'", (report_date,))
        present_staff = cursor.fetchone()[0] or 0

        cursor.execute("""
            SELECT COUNT(DISTINCT lr.employee_id) 
            FROM employee_leave_requests lr
            WHERE lr.status = 'Approved' AND ? BETWEEN lr.start_date AND lr.end_date
        """, (report_date,))
        leave_staff = cursor.fetchone()[0] or 0

        cursor.execute("SELECT COUNT(*) FROM employees WHERE status = 'Active'")
        total_active = cursor.fetchone()[0] or 0

        attendance_summary = {
            "staff_worked": present_staff,
            "staff_leave": leave_staff,
            "staff_duty": max(total_active - leave_staff, present_staff),
            "casual_worked": 0,
            "casual_leave": 0,
            "casual_duty": 0
        }

        # 3. Incoming Material (Inward Purchase Invoices on Date)
        cursor.execute("""
            SELECT p.id, p.purchase_invoice_number as invoice_number, p.invoice_date, pr.company_name as supplier_name, 
                   m.material_name as material_name, pi.quantity, pi.rate, pi.amount
            FROM purchase_invoice p
            JOIN party pr ON p.supplier_id = pr.id
            JOIN purchase_invoice_item pi ON p.id = pi.purchase_invoice_id
            JOIN material m ON pi.material_id = m.id
            WHERE p.invoice_date = ? AND p.status NOT IN ('DRAFT', 'CANCELLED')
            ORDER BY p.id ASC
        """, (report_date,))
        purch_rows = cursor.fetchall()
        incoming_materials = []
        material_summary = {}

        for idx, pr in enumerate(purch_rows, 1):
            d = _row_to_dict(cursor, pr)
            qty = d.get("quantity") or 0.0
            mat_name = d.get("material_name", "E-waste Material")
            incoming_materials.append({
                "sno": idx,
                "igp_no": f"IGP-{d.get('id', idx):04d}",
                "procurement_inv": d.get("invoice_number", ""),
                "supplier_name": d.get("supplier_name", "Vendor"),
                "nomenclature": mat_name,
                "qty": int(qty),
                "weight": float(qty),
                "total_weight": float(qty)
            })

            mk = mat_name.strip().lower()
            if mk not in material_summary:
                material_summary[mk] = {"received_qty": 0, "received_weight": 0.0, "sold_qty": 0, "sold_weight": 0.0, "rate": 0.0}
            material_summary[mk]["received_qty"] += int(qty)
            material_summary[mk]["received_weight"] += float(qty)
            if d.get("rate"):
                material_summary[mk]["rate"] = float(d["rate"])

        # 4. Outgoing Material (Sales Invoices on Date)
        cursor.execute("""
            SELECT s.id, s.invoice_number, s.invoice_date, pr.company_name as buyer_name, 
                   m.material_name as material_name, si.quantity, si.rate, si.amount
            FROM sales_invoice s
            JOIN party pr ON s.party_id = pr.id
            JOIN sales_invoice_item si ON s.id = si.sales_invoice_id
            JOIN material m ON si.material_id = m.id
            WHERE s.invoice_date = ? AND s.status NOT IN ('DRAFT', 'CANCELLED')
            ORDER BY s.id ASC
        """, (report_date,))
        sales_rows = cursor.fetchall()
        outgoing_materials = []
        for idx, sr in enumerate(sales_rows, 1):
            d = _row_to_dict(cursor, sr)
            qty = d.get("quantity") or 0.0
            mat_name = d.get("material_name", "Recycled Material")
            outgoing_materials.append({
                "sno": idx,
                "dispatch_no": f"DSP-{d.get('id', idx):04d}",
                "sales_inv": d.get("invoice_number", ""),
                "buyer_name": d.get("buyer_name", "Buyer"),
                "nomenclature": mat_name,
                "qty": int(qty),
                "weight": float(qty),
                "total_weight": float(qty)
            })

            mk = mat_name.strip().lower()
            if mk not in material_summary:
                material_summary[mk] = {"received_qty": 0, "received_weight": 0.0, "sold_qty": 0, "sold_weight": 0.0, "rate": 0.0}
            material_summary[mk]["sold_qty"] += int(qty)
            material_summary[mk]["sold_weight"] += float(qty)
            if d.get("rate"):
                material_summary[mk]["rate"] = float(d["rate"])

        # 5. Disposal Queue Items
        cursor.execute("""
            SELECT material_name, SUM(weight) as total_weight, SUM(quantity) as total_qty
            FROM disposal_queue
            WHERE generated_date = ? OR status IN ('Pending', 'Disposed')
            GROUP BY LOWER(material_name)
        """, (report_date,))
        disp_rows = cursor.fetchall()
        disposal_queue_summary = {}
        for r in disp_rows:
            d = _row_to_dict(cursor, r)
            mk = d["material_name"].strip().lower()
            disposal_queue_summary[mk] = {
                "weight": float(d["total_weight"] or 0.0),
                "qty": float(d["total_qty"] or 0.0)
            }

        # 6. Inventory Balances
        cursor.execute("""
            SELECT m.material_name as material_name, ib.current_quantity, ib.current_weight
            FROM inventory_balance ib
            JOIN material m ON ib.material_id = m.id
            WHERE ib.current_quantity > 0 OR ib.current_weight > 0
        """)
        inv_rows = cursor.fetchall()
        inventory_dict = {}
        for r in inv_rows:
            d = _row_to_dict(cursor, r)
            mat_name = d["material_name"]
            inventory_dict[mat_name.lower()] = {
                "qty": d["current_quantity"],
                "weight": d["current_weight"]
            }

        return {
            "company": company_info,
            "report_date": report_date,
            "attendance": attendance_summary,
            "incoming_materials": incoming_materials,
            "outgoing_materials": outgoing_materials,
            "material_summary": material_summary,
            "disposal_queue_summary": disposal_queue_summary,
            "inventory": inventory_dict
        }
    finally:
        if close_conn:
            conn.close()


def save_report_history(data, conn=None):
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        cursor = conn.cursor()
        dt = datetime.datetime.strptime(data["report_date"], "%Y-%m-%d")
        cursor.execute("""
            INSERT INTO factory_report_history (
                report_date, report_month, report_year, template_version,
                file_path, file_name, file_size, generated_by, status, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data["report_date"],
            dt.month,
            dt.year,
            data.get("template_version", "v1.0"),
            data["file_path"],
            data["file_name"],
            data.get("file_size", 0),
            data.get("generated_by", "System"),
            data.get("status", "Generated"),
            json.dumps(data.get("metadata", {}))
        ))
        report_id = cursor.lastrowid
        if close_conn:
            conn.commit()
        return report_id
    finally:
        if close_conn:
            conn.close()


def get_report_history(limit=50, conn=None):
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM factory_report_history ORDER BY id DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        return [_row_to_dict(cursor, r) for r in rows]
    finally:
        if close_conn:
            conn.close()


def get_report_by_id(report_id, conn=None):
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM factory_report_history WHERE id = ?", (report_id,))
        row = cursor.fetchone()
        return _row_to_dict(cursor, row)
    finally:
        if close_conn:
            conn.close()
