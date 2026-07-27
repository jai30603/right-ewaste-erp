"""
KPI Engine
Dynamic KPI computation from database-stored formulas.
Every dashboard metric card can be reconfigured at runtime.
"""
import logging
from datetime import datetime, date
from database import get_connection

logger = logging.getLogger(__name__)


def compute_kpi(kpi_key: str) -> dict:
    """Compute a single KPI by evaluating its stored SQL formula."""
    conn = get_connection()
    try:
        kpi = conn.execute(
            "SELECT * FROM kpi_definitions WHERE kpi_key=? AND is_active=1",
            (kpi_key,)
        ).fetchone()
        if not kpi:
            return {"kpi_key": kpi_key, "value": 0, "error": "KPI not found"}

        kpi = dict(kpi)
        value = 0

        if kpi['formula_type'] == 'SQL':
            try:
                row = conn.execute(kpi['formula']).fetchone()
                value = row[0] if row else 0
                value = round(float(value), 2) if value is not None else 0
            except Exception as e:
                logger.warning(f"KPI formula failed for {kpi_key}: {e}")
                value = 0

        result = {
            "kpi_key": kpi_key,
            "kpi_name": kpi['kpi_name'],
            "kpi_category": kpi['kpi_category'],
            "value": value,
            "unit": kpi['unit'],
            "target_value": kpi.get('target_value'),
            "warning_threshold": kpi.get('warning_threshold'),
            "critical_threshold": kpi.get('critical_threshold'),
            "computed_at": datetime.now().isoformat(),
            "status": _get_status(value, kpi),
        }
        return result
    finally:
        conn.close()


def _get_status(value, kpi):
    crit = kpi.get('critical_threshold')
    warn = kpi.get('warning_threshold')
    if crit is not None and value >= crit:
        return 'CRITICAL'
    if warn is not None and value >= warn:
        return 'WARNING'
    return 'OK'


def compute_all_kpis() -> list:
    """Compute all active KPIs."""
    conn = get_connection()
    kpis = conn.execute("SELECT kpi_key FROM kpi_definitions WHERE is_active=1").fetchall()
    conn.close()
    results = []
    for (kpi_key,) in kpis:
        try:
            results.append(compute_kpi(kpi_key))
        except Exception as e:
            logger.warning(f"Failed to compute KPI {kpi_key}: {e}")
            results.append({"kpi_key": kpi_key, "value": 0, "error": str(e)})
    return results


def snapshot_kpis():
    """Save current KPI values to kpi_snapshots (called by scheduler daily)."""
    conn = get_connection()
    kpis = conn.execute("SELECT kpi_key FROM kpi_definitions WHERE is_active=1").fetchall()
    today = date.today().isoformat()
    for (kpi_key,) in kpis:
        try:
            result = compute_kpi(kpi_key)
            conn.execute(
                "INSERT OR REPLACE INTO kpi_snapshots (kpi_key, snapshot_date, value) VALUES (?,?,?)",
                (kpi_key, today, result['value'])
            )
        except Exception as e:
            logger.warning(f"Snapshot failed for {kpi_key}: {e}")
    conn.commit()
    conn.close()


def get_kpi_history(kpi_key: str, days: int = 30) -> list:
    """Retrieve historical KPI snapshots."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT snapshot_date, value FROM kpi_snapshots
        WHERE kpi_key=? ORDER BY snapshot_date DESC LIMIT ?
    """, (kpi_key, days)).fetchall()
    conn.close()
    return [{"date": r[0], "value": r[1]} for r in rows]
