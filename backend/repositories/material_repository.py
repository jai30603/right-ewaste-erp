from database import get_connection


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


def get_material_by_id(material_id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM material WHERE id = ?",
        (material_id,)
    )

    material = cursor.fetchone()

    conn.close()

    return material

def add_material(
    material_code,
    material_name,
    hsn_code,
    uom,
    gst_percentage,
    description
):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO material(
            material_code,
            material_name,
            hsn_code,
            uom,
            gst_percentage,
            description
        )
        VALUES(?,?,?,?,?,?)
    """,(
        material_code,
        material_name,
        hsn_code,
        uom,
        gst_percentage,
        description
    ))

    conn.commit()
    conn.close()

def update_material_rate(material_id, gst_percentage):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE material
        SET gst_percentage = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """,(gst_percentage, material_id))

    conn.commit()
    conn.close()

def delete_material(material_id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE material
        SET is_active = 0,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """,(material_id,))

    conn.commit()
    conn.close()

def search_material(keyword):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM material
        WHERE material_name LIKE ?
          AND is_active = 1
    """,(f"%{keyword}%",))

    materials = cursor.fetchall()

    conn.close()

    return materials