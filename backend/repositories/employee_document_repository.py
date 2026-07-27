import sqlite3
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


def get_documents_by_employee_id(employee_id, conn=None):
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM employee_documents WHERE employee_id = ? ORDER BY id DESC", (employee_id,))
        rows = cursor.fetchall()
        return [_row_to_dict(cursor, r) for r in rows]
    finally:
        if close_conn:
            conn.close()


def get_document_by_id(doc_id, conn=None):
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM employee_documents WHERE id = ?", (doc_id,))
        row = cursor.fetchone()
        return _row_to_dict(cursor, row)
    finally:
        if close_conn:
            conn.close()


def save_document(data, conn=None):
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO employee_documents (
                employee_id, document_category, document_name, file_path,
                file_size, file_type, uploaded_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            data["employee_id"],
            data["document_category"],
            data["document_name"],
            data["file_path"],
            data.get("file_size", 0),
            data.get("file_type"),
            data.get("uploaded_by", "System")
        ))
        doc_id = cursor.lastrowid
        if close_conn:
            conn.commit()
        return doc_id
    finally:
        if close_conn:
            conn.close()


def delete_document(doc_id, conn=None):
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM employee_documents WHERE id = ?", (doc_id,))
        if close_conn:
            conn.commit()
        return True
    finally:
        if close_conn:
            conn.close()
