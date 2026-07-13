from database import get_connection


def generate_material_code():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT MAX(CAST(SUBSTR(material_code, 5) AS INTEGER)) FROM material"
    )
    max_num = cursor.fetchone()[0] or 0
    conn.close()
    return f"MAT-{(max_num + 1):05d}"


def get_all_materials():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT *
        FROM material
        WHERE is_active = 1
        ORDER BY material_name
    """)
    materials = cursor.fetchall()
    conn.close()
    return materials


def search_materials(keyword):
    conn = get_connection()
    cursor = conn.cursor()
    like = f"%{keyword}%"
    cursor.execute("""
        SELECT *
        FROM material
        WHERE is_active = 1
          AND (
              material_code LIKE ? OR
              material_name LIKE ? OR
              category      LIKE ? OR
              hsn_code      LIKE ?
          )
        ORDER BY material_name
    """, (like, like, like, like))
    materials = cursor.fetchall()
    conn.close()
    return materials


def get_material_by_id(material_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM material WHERE id = ?", (material_id,))
    material = cursor.fetchone()
    conn.close()
    return material


def add_material(
    material_name, category, hsn_code,
    uom, gst_percentage, description, tracking_type='BOTH'
):
    material_code = generate_material_code()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO material (
            material_code, material_name, category,
            hsn_code, uom, gst_percentage, description, tracking_type
        ) VALUES (?,?,?,?,?,?,?,?)
    """, (
        material_code, material_name, category or None,
        hsn_code or None, uom, gst_percentage, description or None, tracking_type
    ))
    conn.commit()
    conn.close()


def update_material(
    material_id,
    material_name, category, hsn_code,
    uom, gst_percentage, description, tracking_type='BOTH'
):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE material SET
            material_name  = ?,
            category       = ?,
            hsn_code       = ?,
            uom            = ?,
            gst_percentage = ?,
            description    = ?,
            tracking_type  = ?,
            updated_at     = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (
        material_name, category or None, hsn_code or None,
        uom, gst_percentage, description or None, tracking_type,
        material_id
    ))
    conn.commit()
    conn.close()


def delete_material(material_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE material
        SET is_active  = 0,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (material_id,))
    conn.commit()
    conn.close()
