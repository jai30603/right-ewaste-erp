import logging
from datetime import datetime
from database import get_connection

logger = logging.getLogger(__name__)


# ── Invoice number ────────────────────────────────────────────────────────────

def _generate_invoice_number(cursor):
    """
    Must be called inside an open transaction so the MAX read and the
    subsequent INSERT are atomic — prevents duplicate numbers under concurrent
    requests.
    """
    year = datetime.now().year
    cursor.execute(
        "SELECT MAX(CAST(SUBSTR(invoice_number, 10) AS INTEGER)) "
        "FROM sales_invoice WHERE invoice_number LIKE ?",
        (f"INV-{year}-%",)
    )
    max_num = cursor.fetchone()[0] or 0
    return f"INV-{year}-{(max_num + 1):05d}"


# ── GST calculation ───────────────────────────────────────────────────────────

def calculate_gst(subtotal, items_gst, company_state_code, party_state_code):
    """
    items_gst: list of {"amount": float, "gst_percentage": float}
    Returns dict: cgst, sgst, igst, round_off, grand_total.
    Intra-state  → CGST + SGST (equal halves).
    Inter-state  → IGST (full GST amount).
    """
    total_gst = sum(
        i["amount"] * i["gst_percentage"] / 100
        for i in items_gst
    )
    intra = str(company_state_code).strip() == str(party_state_code).strip()
    cgst  = round(total_gst / 2, 2) if intra else 0.0
    sgst  = round(total_gst / 2, 2) if intra else 0.0
    igst  = 0.0 if intra else round(total_gst, 2)

    grand_raw   = subtotal + cgst + sgst + igst
    grand_round = round(grand_raw)
    round_off   = round(grand_round - grand_raw, 2)

    return {
        "cgst":        cgst,
        "sgst":        sgst,
        "igst":        igst,
        "round_off":   round_off,
        "grand_total": float(grand_round),
    }


# ── Read queries ──────────────────────────────────────────────────────────────

def get_all_invoices():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            si.*,
            p.company_name,
            (SELECT COUNT(*) FROM sales_invoice_item
             WHERE sales_invoice_id = si.id) AS item_count
        FROM sales_invoice si
        LEFT JOIN party p ON si.party_id = p.id
        ORDER BY si.created_at DESC
    """)
    invoices = cursor.fetchall()
    conn.close()
    return invoices


def get_invoice_by_id(invoice_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT si.*, p.company_name
        FROM sales_invoice si
        LEFT JOIN party p ON si.party_id = p.id
        WHERE si.id = ?
    """, (invoice_id,))
    invoice = cursor.fetchone()
    conn.close()
    return invoice


def get_invoice_items(invoice_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT sii.*, m.material_name, m.uom, m.gst_percentage
        FROM sales_invoice_item sii
        LEFT JOIN material m ON sii.material_id = m.id
        WHERE sii.sales_invoice_id = ?
        ORDER BY sii.id
    """, (invoice_id,))
    items = cursor.fetchall()
    conn.close()
    return items


# ── Create (transactional) ────────────────────────────────────────────────────

def create_sales_invoice(
    party_id, invoice_date, payment_mode,
    transporter, vehicle_number, remarks,
    items,               # list of dicts: material_id, qty, weight, pieces, rate, amount, gst_percentage
    company_state_code,
    party_state_code,
):
    """
    Saves the invoice header and all line-items inside a single explicit
    database transaction.

    On success  → commits and returns the new invoice_id.
    On any error → rolls back every INSERT so no partial data is written,
                   then re-raises the exception for the route to handle.
    """
    subtotal = round(sum(i["amount"] for i in items), 2)
    gst      = calculate_gst(subtotal, items, company_state_code, party_state_code)

    conn   = get_connection()
    cursor = conn.cursor()

    try:
        # ── BEGIN explicit transaction ────────────────────────────────────
        conn.execute("BEGIN")

        # ── Step 1: generate invoice number (inside transaction) ──────────
        invoice_number = _generate_invoice_number(cursor)
        logger.info("Creating invoice %s for party_id=%s", invoice_number, party_id)

        # ── Step 2: insert invoice header ─────────────────────────────────
        cursor.execute("""
            INSERT INTO sales_invoice (
                invoice_number, invoice_date, party_id,
                payment_mode, transporter, vehicle_number,
                subtotal, cgst, sgst, igst, round_off, grand_total,
                remarks, status
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            invoice_number, invoice_date, party_id,
            payment_mode  or None,
            transporter   or None,
            vehicle_number or None,
            subtotal,
            gst["cgst"], gst["sgst"], gst["igst"],
            gst["round_off"], gst["grand_total"],
            remarks or None,
            "CONFIRMED",
        ))

        invoice_id = cursor.lastrowid
        logger.info("Invoice header saved — id=%s", invoice_id)

        # ── Step 3: insert every line-item ────────────────────────────────
        for idx, item in enumerate(items, start=1):
            cursor.execute("""
                INSERT INTO sales_invoice_item
                    (sales_invoice_id, material_id,
                     quantity, weight, pieces, rate, amount)
                VALUES (?,?,?,?,?,?,?)
            """, (
                invoice_id,
                item["material_id"],
                item["qty"],
                item["weight"],
                item["pieces"],
                item["rate"],
                item["amount"],
            ))
            logger.debug("  item %d saved (material_id=%s)", idx, item["material_id"])

        # ── Step 4: commit only when every insert succeeded ───────────────
        conn.execute("COMMIT")
        logger.info("Invoice %s committed successfully (%d items)", invoice_number, len(items))
        return invoice_id

    except Exception as exc:
        # ── Rollback — neither header nor items will persist ──────────────
        conn.execute("ROLLBACK")
        logger.error(
            "Invoice creation failed — rolled back. Error: %s", exc, exc_info=True
        )
        raise RuntimeError(f"Invoice save failed and was rolled back: {exc}") from exc

    finally:
        conn.close()
