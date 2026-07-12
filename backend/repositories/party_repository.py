from database import get_connection


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


def get_party_by_id(party_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM party WHERE id = ? AND is_active = 1",
        (party_id,)
    )

    party = cursor.fetchone()

    conn.close()

    return party

def generate_party_code():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM party")

    count = cursor.fetchone()[0]

    conn.close()

    return f"PTY-{count:05d}"

def add_party(
    company_name,
    contact_person,
    party_type,
    gstin,
    pan,
    phone,
    alternate_phone,
    email,
    billing_address,
    shipping_address,
    city,
    state,
    state_code,
    pincode,
    remarks
):

    conn = get_connection()
    cursor = conn.cursor()

    # Keep number allocation and insertion in one write transaction.
    try:
        cursor.execute("BEGIN IMMEDIATE")
        cursor.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM party")
        party_code = f"PTY-{cursor.fetchone()[0]:05d}"

        cursor.execute("""
        INSERT INTO party(
            party_code,
            company_name,
            contact_person,
            party_type,
            gstin,
            pan,
            phone,
            alternate_phone,
            email,
            billing_address,
            shipping_address,
            city,
            state,
            state_code,
            pincode,
            remarks
        )

        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,(
        party_code,
        company_name,
        contact_person,
        party_type,
        gstin,
        pan,
        phone,
        alternate_phone,
        email,
        billing_address,
        shipping_address,
        city,
        state,
        state_code,
        pincode,
        remarks
        ))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def update_party_phone(party_id, phone):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE party
        SET phone = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (phone, party_id)
    )

    conn.commit()
    conn.close()

def delete_party(party_id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE party
        SET is_active = 0,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (party_id,)
    )

    conn.commit()
    conn.close()

def search_party(keyword):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM party
        WHERE is_active = 1
        AND company_name LIKE ?
        ORDER BY company_name
    """, (f"%{keyword}%",))

    parties = cursor.fetchall()

    conn.close()

    return parties

def update_party(
    party_id,
    company_name,
    contact_person,
    party_type,
    gstin,
    pan,
    phone,
    alternate_phone,
    email,
    billing_address,
    shipping_address,
    city,
    state,
    state_code,
    pincode,
    remarks
):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE party
        SET
            company_name = ?,
            contact_person = ?,
            party_type = ?,
            gstin = ?,
            pan = ?,
            phone = ?,
            alternate_phone = ?,
            email = ?,
            billing_address = ?,
            shipping_address = ?,
            city = ?,
            state = ?,
            state_code = ?,
            pincode = ?,
            remarks = ?,
            updated_at = CURRENT_TIMESTAMP

        WHERE id = ? AND is_active = 1
    """, (

        company_name,
        contact_person,
        party_type,
        gstin,
        pan,
        phone,
        alternate_phone,
        email,
        billing_address,
        shipping_address,
        city,
        state,
        state_code,
        pincode,
        remarks,
        party_id

    ))

    try:
        conn.commit()
        return cursor.rowcount
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
