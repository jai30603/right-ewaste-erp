from datetime import datetime
from uuid import uuid4

from database import get_connection
from repositories import inventory_repository


STATES = {"RAW", "PROCESSING", "RECOVERED", "FINISHED", "RESERVED", "REJECTED", "DISPOSED"}
MOVEMENT_TYPES = {
    "PURCHASE", "SALE", "PROCESSING", "REFURBISHMENT", "DISMANTLING", "SORTING",
    "INTERNAL_CONSUMPTION", "WEIGHT_ADJUSTMENT", "MANUAL_ADJUSTMENT", "RETURN", "TRANSFER",
}


class InventoryError(ValueError):
    pass


def calculate_running_balance(ledger_rows):
    """Compatibility helper for legacy callers; V2 ledger rows already retain before/after values."""
    balance = 0.0
    ledger = []
    for row in ledger_rows:
        item = dict(row)
        if "quantity_after" in item:
            item["balance"] = float(item["quantity_after"] or 0)
        else:
            qty = float(item.get("qty") or 0)
            balance += qty if item.get("type") == "Purchase" else -qty
            item["balance"] = balance
        ledger.append(item)
    return ledger


def _validate_movement(material_id, inventory_state, movement_type, quantity_change, weight_change, conn):
    if inventory_state not in STATES:
        raise InventoryError("Invalid inventory state.")
    if movement_type not in MOVEMENT_TYPES:
        raise InventoryError("Invalid stock movement type.")
    material = conn.execute("SELECT id FROM material WHERE id = ? AND is_active = 1", (material_id,)).fetchone()
    if not material:
        raise InventoryError("Invalid or inactive material selected.")
    current = inventory_repository.get_stock(material_id, inventory_state, 1, conn)
    if (
        current["current_quantity"] + quantity_change < -0.000001
        or current["current_weight"] + weight_change < -0.000001
    ):
        raise InventoryError("Insufficient stock available.")


def record_movement(
    *, material_id, movement_type, reference_type, reference_number, quantity_change=0,
    weight_change=0, inventory_state="RAW", reference_id=None,
    performed_by="System User", remarks=None, movement_key=None, created_at=None,
    processing_job_reference=None, certificate_reference=None,
):
    quantity_change = float(quantity_change or 0)
    weight_change = float(weight_change or 0)
    if not any((quantity_change, weight_change)):
        raise InventoryError("A stock movement must change quantity or weight.")

    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        _validate_movement(material_id, inventory_state, movement_type, quantity_change, weight_change, conn)
        inventory_repository.apply_movement({
            "movement_key": movement_key or uuid4().hex,
            "material_id": material_id,
            "warehouse_id": 1,
            "inventory_state": inventory_state,
            "movement_type": movement_type,
            "reference_type": reference_type,
            "reference_id": reference_id,
            "reference_number": reference_number,
            "quantity_change": quantity_change,
            "weight_change": weight_change,
            "performed_by": performed_by,
            "remarks": remarks,
            "processing_job_reference": processing_job_reference,
            "certificate_reference": certificate_reference,
            "created_at": created_at,
        }, conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def sync_document(document_type, document_id, performed_by="System User"):
    """Synchronize one invoice with its inventory movements after create, edit, or soft delete."""
    if document_type not in {"PURCHASE", "SALE"}:
        raise InventoryError("Unsupported inventory document type.")
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        inventory_repository.remove_source_movements(document_type, document_id, conn)
        rows = inventory_repository.get_document_items(document_type, document_id, conn)
        if rows and rows[0]["is_active"] and rows[0]["status"] not in {"DRAFT", "CANCELLED"}:
            multiplier = 1 if document_type == "PURCHASE" else -1
            movement_type = "PURCHASE" if document_type == "PURCHASE" else "SALE"
            from repositories import batch_repository, material_repository

            for row in rows:
                row_dict = dict(row)
                
                # Skip inventory tracking for service / charge items or non-material lines
                is_service = False
                if document_type == "SALE" and row_dict.get("item_type") == "Service/Charge":
                    is_service = True
                if row_dict.get("material_id") == 999999 or row_dict.get("tracking_type") == "NONE" or not row_dict.get("material_id"):
                    is_service = True
                
                if is_service:
                    continue

                quantity = multiplier * float(row_dict.get("quantity") or 0)
                weight = multiplier * float(row_dict.get("weight") or 0)
                
                # Batch creation / retrieval for Purchase Document
                batch_id = None
                batch_number = None

                if document_type == "PURCHASE":
                    # Check if batch exists for this purchase invoice item
                    existing_b = conn.execute(
                        "SELECT id, batch_number FROM material_batch WHERE purchase_invoice_id = ? AND material_id = ?",
                        (document_id, row_dict["material_id"])
                    ).fetchone()

                    if existing_b:
                        batch_id = existing_b[0]
                        batch_number = existing_b[1]
                    else:
                        mat_info = material_repository.get_material_by_id(row_dict["material_id"])
                        mat_name = mat_info["material_name"] if mat_info else "Material"
                        b_id, b_num = batch_repository.create_batch({
                            "purchase_invoice_id": document_id,
                            "purchase_invoice_number": row_dict.get("document_number"),
                            "supplier_id": row_dict.get("supplier_id"),
                            "supplier_name": row_dict.get("supplier_name", "") or row_dict.get("company_name", ""),
                            "purchase_date": row_dict.get("invoice_date"),
                            "material_id": row_dict["material_id"],
                            "material_name": mat_name,
                            "quantity": float(row_dict.get("quantity") or 0),
                            "weight": float(row_dict.get("weight") or 0),
                            "remaining_quantity": float(row_dict.get("quantity") or 0),
                            "remaining_weight": float(row_dict.get("weight") or 0),
                            "warehouse_id": 1,
                            "status": "IN_STORE",
                            "financial_valuation": float(row_dict.get("amount") or 0.0)
                        }, conn)
                        batch_id = b_id
                        batch_number = b_num

                # Determine state dynamically (deduct from where stock exists)
                state = "RAW"
                if document_type == "SALE":
                    st_row = conn.execute(
                        "SELECT inventory_state FROM inventory_balance WHERE material_id = ? AND current_quantity > 0 ORDER BY current_quantity DESC LIMIT 1",
                        (row_dict["material_id"],)
                    ).fetchone()
                    if st_row:
                        state = st_row[0]

                # Legacy invoices can predate inventory tracking or contain historical
                # discrepancies. Preserve the sale and make the gap explicit rather
                # than creating a negative balance during the one-time migration.
                if document_type == "SALE" and performed_by == "System Migration":
                    current = inventory_repository.get_stock(row_dict["material_id"], state, 1, conn)
                    opening_quantity = max(0.0, -quantity - current["current_quantity"])
                    opening_weight = max(0.0, -weight - current["current_weight"])
                    if any((opening_quantity, opening_weight)):
                        inventory_repository.apply_movement({
                            "movement_key": f"OPENING:{row_dict['item_id']}",
                            "material_id": row_dict["material_id"], "warehouse_id": 1, "inventory_state": state,
                            "movement_type": "MANUAL_ADJUSTMENT", "reference_type": "SYSTEM_MIGRATION",
                            "reference_id": document_id, "reference_number": "System Migration Opening Balance",
                            "quantity_change": opening_quantity, "weight_change": opening_weight,
                            "performed_by": performed_by,
                            "remarks": "Opening balance created to reconcile legacy sale history.",
                            "created_at": f"{row_dict['invoice_date']} 00:00:00",
                        }, conn)
                _validate_movement(row_dict["material_id"], state, movement_type, quantity, weight, conn)
                inventory_repository.apply_movement({
                    "movement_key": f"{document_type}:{row_dict['item_id']}",
                    "material_id": row_dict["material_id"], "warehouse_id": 1, "inventory_state": state,
                    "movement_type": movement_type, "reference_type": document_type,
                    "reference_id": document_id, "reference_number": row_dict.get("document_number"),
                    "quantity_change": quantity, "weight_change": weight,
                    "batch_id": batch_id,
                    "batch_number": batch_number,
                    "performed_by": performed_by, "remarks": None,
                    "created_at": f"{row_dict.get('invoice_date', '')} 00:00:00",
                }, conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def bootstrap_inventory():
    """Backfill V2 movements once from confirmed legacy purchase and sales documents."""
    conn = get_connection()
    try:
        complete = conn.execute("SELECT 1 FROM inventory_metadata WHERE key = 'v2_backfill_complete'").fetchone()
        if complete:
            return
        conn.execute("DELETE FROM stock_movement")
        conn.execute("DELETE FROM inventory_balance")
        conn.commit()
        purchase_ids = [row[0] for row in conn.execute("SELECT id FROM purchase_invoice ORDER BY invoice_date, id")]
        sales_ids = [row[0] for row in conn.execute("SELECT id FROM sales_invoice ORDER BY invoice_date, id")]
    finally:
        conn.close()
    for invoice_id in purchase_ids:
        sync_document("PURCHASE", invoice_id, "System Migration")
    for invoice_id in sales_ids:
        sync_document("SALE", invoice_id, "System Migration")
    conn = get_connection()
    try:
        conn.execute("INSERT OR REPLACE INTO inventory_metadata (key, value, updated_at) VALUES ('v2_backfill_complete', '1', CURRENT_TIMESTAMP)")
        conn.commit()
    finally:
        conn.close()


def adjust_stock(material_id, direction, quantity, weight, reason, performed_by):
    if not reason or not reason.strip():
        raise InventoryError("An adjustment reason is required.")
    if direction not in {"IN", "OUT"}:
        raise InventoryError("Invalid adjustment direction.")
    sign = 1 if direction == "IN" else -1
    record_movement(
        material_id=material_id,
        movement_type="MANUAL_ADJUSTMENT",
        reference_type="MANUAL_ADJUSTMENT",
        reference_number=f"ADJ-{datetime.now():%Y%m%d}-{uuid4().hex[:6].upper()}",
        quantity_change=sign * float(quantity or 0),
        weight_change=sign * float(weight or 0),
        performed_by=performed_by,
        remarks=reason.strip(),
    )
