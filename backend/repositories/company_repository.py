

from database import get_connection

def get_company():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM company")

    company = cursor.fetchone()

    conn.close()

    return company