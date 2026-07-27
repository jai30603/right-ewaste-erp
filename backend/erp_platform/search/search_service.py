import sqlite3
from database import get_connection


class GlobalSearchService:
    _providers = {}

    @classmethod
    def register_provider(cls, name, provider_func):
        cls._providers[name] = provider_func

    @classmethod
    def global_search(cls, query):
        if not query or not query.strip():
            return []

        results = []
        for name, func in cls._providers.items():
            try:
                res = func(query.strip())
                if res:
                    results.extend(res)
            except Exception:
                pass
        return results


def search_employees_provider(query_str):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        s = f"%{query_str}%"
        cursor.execute("""
            SELECT id, employee_code, full_name, department, designation, email, mobile_number, status
            FROM employees
            WHERE employee_code LIKE ? OR full_name LIKE ? OR email LIKE ? OR mobile_number LIKE ? OR department LIKE ? OR designation LIKE ?
            LIMIT 10
        """, (s, s, s, s, s, s))
        rows = cursor.fetchall()
        results = []
        for r in rows:
            desc = [d[0] for d in cursor.description]
            row_dict = dict(zip(desc, r))
            results.append({
                "type": "Employee",
                "title": f"{row_dict['full_name']} ({row_dict['employee_code']})",
                "subtitle": f"{row_dict.get('designation') or 'Staff'} - {row_dict.get('department') or 'General'} ({row_dict['status']})",
                "url": f"/employees/{row_dict['id']}",
                "id": row_dict["id"]
            })
        return results
    finally:
        conn.close()


# Register Employee Provider automatically
GlobalSearchService.register_provider("employee", search_employees_provider)
