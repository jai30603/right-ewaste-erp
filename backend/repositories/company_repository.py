

from database import get_connection

def get_company():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM company")
    company = cursor.fetchone()
    conn.close()
    return company

def update_company(data):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE company SET
            company_name = ?,
            address_line_1 = ?,
            address_line_2 = ?,
            city = ?,
            state = ?,
            state_code = ?,
            pincode = ?,
            gstin = ?,
            pan = ?,
            cin = ?,
            phone = ?,
            email = ?,
            website = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = 1
    """, (
        data["company_name"],
        data["address_line_1"],
        data.get("address_line_2"),
        data["city"],
        data["state"],
        data["state_code"],
        data["pincode"],
        data["gstin"],
        data["pan"],
        data.get("cin"),
        data["phone"],
        data.get("email"),
        data.get("website")
    ))
    conn.commit()
    conn.close()