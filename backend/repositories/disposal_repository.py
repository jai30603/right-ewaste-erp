import logging
from database import get_connection

logger = logging.getLogger(__name__)

# Default Disposal Types
DEFAULT_DISPOSAL_TYPES = [
    ("Authorized Recycler", "Disposal through CPCB/SPCB authorized recyclers"),
    ("Hazardous Waste Facility", "Treatment and disposal at TSDF facilities"),
    ("Landfill", "Approved industrial landfill site"),
    ("Incineration", "Thermal destruction at authorized incinerator"),
    ("Return to Supplier", "Take-back or EPR return to OEM/supplier"),
    ("Internal Destruction", "In-house mechanical or physical destruction"),
    ("Transfer to Another Branch", "Inter-branch transfer for specialized handling"),
    ("General Waste", "Non-hazardous municipal municipal waste collection"),
    ("Other", "Custom disposal method")
]

# Default Disposal Materials
DEFAULT_DISPOSAL_MATERIALS = [
    ("DISP-BAT-W", "Battery Lead Acid Water", "Hazardous Batteries", 1, "KGS"),
    ("DISP-BAT-SMF", "Battery Lead Acid SMF Small", "Hazardous Batteries", 1, "KGS"),
    ("DISP-BAT-DRY", "Battery Lead Acid SMF Dry", "Hazardous Batteries", 1, "KGS"),
    ("DISP-BAT-LAP", "Laptop Battery", "Lithium Ion Batteries", 1, "PCS"),
    ("DISP-BAT-MOB", "Mobile Battery", "Lithium Ion Batteries", 1, "PCS"),
    ("DISP-BAT-CELL", "Dry Cell Battery", "Hazardous Batteries", 1, "PCS"),
    ("DISP-CAP-CON", "Capacitor & Condenser", "Electronic Waste", 1, "KGS"),
    ("DISP-DISP-LCD", "LCD Display Waste", "Glass & Electronic Waste", 1, "PCS"),
    ("DISP-CRT-GLA", "CRT Glass", "Hazardous Glass", 1, "KGS"),
    ("DISP-GLA-WAS", "Glass Waste", "General Glass", 1, "KGS"),
    ("DISP-MEM-FIL", "Membrane Filter", "Industrial Waste", 1, "PCS"),
    ("DISP-TON-CAD", "Toner Cartridge", "Chemical & Plastic Waste", 1, "PCS"),
    ("DISP-THE-FOA", "Thermocol / Foam", "Packaging Waste", 1, "KGS"),
    ("DISP-WOO-PAL", "Wood / Pallets", "Packaging Waste", 0, "KGS"),
    ("DISP-CAR-BOX", "Carton Box / Paper Waste", "Paper Waste", 0, "KGS"),
    ("DISP-MIX-WAS", "Mixed Waste", "General Waste", 0, "KGS")
]


def seed_default_disposal_masters(conn=None):
    close_conn = False
    if conn is None:
        conn = get_connection()
        close_conn = True

    try:
        cursor = conn.cursor()

        # Seed Disposal Types
        for type_name, desc in DEFAULT_DISPOSAL_TYPES:
            cursor.execute("SELECT id FROM disposal_types_master WHERE type_name = ?", (type_name,))
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO disposal_types_master (type_name, description) VALUES (?, ?)",
                    (type_name, desc)
                )

        # Seed Disposal Materials
        for code, name, cat, is_haz, unit in DEFAULT_DISPOSAL_MATERIALS:
            cursor.execute("SELECT id FROM disposal_material_master WHERE material_code = ?", (code,))
            if not cursor.fetchone():
                cursor.execute(
                    """INSERT INTO disposal_material_master
                       (material_code, material_name, category, is_hazardous, default_unit)
                       VALUES (?, ?, ?, ?, ?)""",
                    (code, name, cat, is_haz, unit)
                )

        if close_conn:
            conn.commit()
    finally:
        if close_conn:
            conn.close()


def get_all_disposal_materials():
    seed_default_disposal_masters()
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM disposal_material_master ORDER BY material_name ASC")
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_all_disposal_types():
    seed_default_disposal_masters()
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM disposal_types_master WHERE is_active = 1 ORDER BY type_name ASC")
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_pending_disposal_queue(query="", category="all"):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        sql = "SELECT dq.* FROM disposal_queue dq WHERE dq.status = 'Pending'"
        params = []

        if query:
            sql += " AND (dq.processing_number LIKE ? OR dq.material_name LIKE ?)"
            params.extend([f"%{query}%", f"%{query}%"])

        sql += " ORDER BY dq.created_at DESC"
        cursor.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_disposal_history(query="", disposal_type="all"):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        sql = "SELECT dq.* FROM disposal_queue dq WHERE dq.status = 'Disposed'"
        params = []

        if query:
            sql += " AND (dq.processing_number LIKE ? OR dq.material_name LIKE ? OR dq.vendor_name LIKE ?)"
            params.extend([f"%{query}%", f"%{query}%", f"%{query}%"])

        if disposal_type != "all" and disposal_type:
            sql += " AND dq.disposal_type = ?"
            params.append(disposal_type)

        sql += " ORDER BY dq.disposed_at DESC"
        cursor.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_disposal_queue_item(item_id):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM disposal_queue WHERE id = ?", (item_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def add_to_disposal_queue(job_id, job_number, material_id, material_name, quantity, weight, unit, generated_date,
                          parent_batch_id=None, parent_batch_number=None, conn=None):
    close_conn = False
    if conn is None:
        conn = get_connection()
        close_conn = True

    try:
        cursor = conn.cursor()
        # Prevent duplicates for same job & material
        cursor.execute(
            """SELECT id FROM disposal_queue
               WHERE processing_job_id = ? AND material_id = ? AND status = 'Pending'""",
            (job_id, material_id)
        )
        row = cursor.fetchone()
        if row:
            # Update existing queue entry weight/quantity
            cursor.execute(
                """UPDATE disposal_queue
                   SET quantity = quantity + ?, weight = weight + ?
                   WHERE id = ?""",
                (quantity, weight, row[0])
            )
            queue_id = row[0]
        else:
            cursor.execute(
                """INSERT INTO disposal_queue
                   (processing_job_id, processing_number, material_id, material_name,
                    quantity, weight, unit, generated_date, parent_batch_id, parent_batch_number, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Pending')""",
                (job_id, job_number, material_id, material_name, quantity, weight, unit, generated_date,
                 parent_batch_id, parent_batch_number)
            )
            queue_id = cursor.lastrowid

        if close_conn:
            conn.commit()
        return queue_id
    finally:
        if close_conn:
            conn.close()


def execute_disposal_item(queue_id, disposal_type, vendor_id, vendor_name, transport_details, document_path, remarks, disposed_by, conn=None):
    close_conn = False
    if conn is None:
        conn = get_connection()
        close_conn = True

    try:
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE disposal_queue
               SET status = 'Disposed',
                   disposal_type = ?,
                   disposal_vendor_id = ?,
                   vendor_name = ?,
                   transport_details = ?,
                   supporting_document_path = ?,
                   remarks = ?,
                   disposed_at = CURRENT_TIMESTAMP,
                   disposed_by = ?
               WHERE id = ?""",
            (disposal_type, vendor_id, vendor_name, transport_details, document_path, remarks, disposed_by, queue_id)
        )

        if close_conn:
            conn.commit()
    finally:
        if close_conn:
            conn.close()
