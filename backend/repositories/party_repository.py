from database import get_connection


def generate_party_code():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT MAX(CAST(SUBSTR(party_code, 5) AS INTEGER)) FROM party"
    )
    max_num = cursor.fetchone()[0] or 0
    conn.close()
    return f"PTY-{(max_num + 1):05d}"


def get_all_parties():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT *
        FROM party
        WHERE is_active = 1
        ORDER BY company_name
    """)
    parties = cursor.fetchall()
    conn.close()
    return parties


def search_parties(keyword):
    conn = get_connection()
    cursor = conn.cursor()
    like = f"%{keyword}%"
    cursor.execute("""
        SELECT *
        FROM party
        WHERE is_active = 1
          AND (
              party_code     LIKE ? OR
              company_name   LIKE ? OR
              contact_person LIKE ? OR
              phone          LIKE ? OR
              gstin          LIKE ?
          )
        ORDER BY company_name
    """, (like, like, like, like, like))
    parties = cursor.fetchall()
    conn.close()
    return parties


def get_party_by_id(party_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM party WHERE id = ?", (party_id,))
    party = cursor.fetchone()
    conn.close()
    return party


def add_party(
    company_name, contact_person, party_type,
    gstin, pan, phone, alternate_phone, email,
    billing_address, shipping_address,
    city, state, state_code, pincode, remarks
):
    party_code = generate_party_code()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO party (
            party_code, company_name, contact_person, party_type,
            gstin, pan, phone, alternate_phone, email,
            billing_address, shipping_address,
            city, state, state_code, pincode, remarks
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        party_code, company_name, contact_person, party_type,
        gstin or None, pan or None, phone, alternate_phone or None,
        email or None, billing_address, shipping_address or None,
        city, state, state_code, pincode or None, remarks or None
    ))
    conn.commit()
    conn.close()


def update_party(
    party_id,
    company_name, contact_person, party_type,
    gstin, pan, phone, alternate_phone, email,
    billing_address, shipping_address,
    city, state, state_code, pincode, remarks
):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE party SET
            company_name   = ?,
            contact_person = ?,
            party_type     = ?,
            gstin          = ?,
            pan            = ?,
            phone          = ?,
            alternate_phone = ?,
            email          = ?,
            billing_address = ?,
            shipping_address = ?,
            city           = ?,
            state          = ?,
            state_code     = ?,
            pincode        = ?,
            remarks        = ?,
            updated_at     = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (
        company_name, contact_person, party_type,
        gstin or None, pan or None, phone, alternate_phone or None,
        email or None, billing_address, shipping_address or None,
        city, state, state_code, pincode or None, remarks or None,
        party_id
    ))
    conn.commit()
    conn.close()


def delete_party(party_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE party
        SET is_active  = 0,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (party_id,))
    conn.commit()
    conn.close()


def get_active_party_states():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT state FROM party WHERE state IS NOT NULL AND state != '' AND is_active = 1")
    states = [row[0] for row in cursor.fetchall()]
    conn.close()
    return states

