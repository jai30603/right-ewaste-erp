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
        "SELECT * FROM party WHERE id = ?",
        (party_id,)
    )

    party = cursor.fetchone()

    conn.close()

    return party

def generate_party_code():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM party")

    count = cursor.fetchone()[0] + 1

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

    party_code = generate_party_code()

    conn = get_connection()
    cursor = conn.cursor()

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

    cursor.execute(
        """
        SELECT *
        FROM party
        WHERE company_name LIKE ?
          AND is_active = 1
        """,
        (f"%{keyword}%",)
    )

    result = cursor.fetchall()

    conn.close()

    return result