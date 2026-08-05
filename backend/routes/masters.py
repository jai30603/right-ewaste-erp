from flask import Blueprint, render_template
from database import get_connection

masters_bp = Blueprint("masters", __name__)


@masters_bp.route("/masters")
def masters_hub():
    """Masters module hub — aggregated stats and quick navigation."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM party WHERE is_active = 1")
        party_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM material WHERE is_active = 1")
        material_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM material_category")
        category_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM unit_of_measure")
        unit_count = cur.fetchone()[0]

        try:
            cur.execute("SELECT COUNT(*) FROM disposal_material_master WHERE is_active = 1")
            disposal_material_count = cur.fetchone()[0]
        except Exception:
            disposal_material_count = 0

        try:
            cur.execute("SELECT COUNT(*) FROM disposal_types_master WHERE is_active = 1")
            disposal_type_count = cur.fetchone()[0]
        except Exception:
            disposal_type_count = 0

    finally:
        conn.close()

    return render_template(
        "masters/hub.html",
        party_count=party_count,
        material_count=material_count,
        category_count=category_count,
        unit_count=unit_count,
        disposal_material_count=disposal_material_count,
        disposal_type_count=disposal_type_count,
    )
