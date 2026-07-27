import logging
from datetime import datetime, date
from uuid import uuid4
from database import get_connection
from repositories import processing_repository, inventory_repository
from services.inventory_service import _validate_movement, InventoryError
from config.business import PROCESSING_WEIGHT_TOLERANCE

logger = logging.getLogger(__name__)

def generate_job_number(conn=None):
    from repositories import settings_repository
    return settings_repository.increment_and_get_number("PROCESSING", conn)

def create_job(job_data, inputs, performed_by):
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        job_data["processing_number"] = generate_job_number(conn)
        job_data["status"] = "DRAFT"
        
        job_id = processing_repository.create_processing_job(job_data, conn)
        processing_repository.save_inputs(job_id, inputs, conn)
        processing_repository.log_job_activity(job_id, "DRAFT", performed_by, "Job created in draft status.", conn)
        conn.commit()
        return job_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def save_draft(job_id, job_data, inputs, outputs, losses, performed_by):
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        job = processing_repository.get_processing_job(job_id)
        if not job:
            raise ValueError("Processing job not found.")
        if job["status"] not in ("DRAFT", "READY"):
            raise ValueError("Only draft or ready jobs can be edited.")
            
        processing_repository.update_processing_job(job_id, job_data, conn)
        processing_repository.save_inputs(job_id, inputs, conn)
        processing_repository.save_outputs(job_id, outputs, conn)
        processing_repository.save_processing_loss(job_id, losses, conn)
        processing_repository.log_job_activity(job_id, job_data["status"], performed_by, "Job draft updated.", conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def start_job(job_id, performed_by):
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        job = processing_repository.get_processing_job(job_id)
        if not job:
            raise ValueError("Processing job not found.")
        if job["status"] not in ("DRAFT", "READY"):
            raise ValueError("Job has already been started or processed.")
            
        # 1. Update job status to IN_PROGRESS
        job_data = {
            "processing_date": job["processing_date"],
            "status": "IN_PROGRESS",
            "priority": job["priority"],
            "operator_id": job["operator_id"],
            "remarks": job["remarks"],
        }
        processing_repository.update_processing_job(job_id, job_data, conn)
        
        # 2. Reserve inputs: deduct RAW and add to RESERVED
        for item in job["inputs"]:
            # Deduct from RAW
            qty = float(item["quantity"])
            wt = float(item["weight"])
            
            # Deduct RAW
            _validate_movement(item["material_id"], "RAW", "TRANSFER", -qty, -wt, conn)
            inventory_repository.apply_movement({
                "movement_key": f"START_RAW:{job_id}:{item['id']}",
                "material_id": item["material_id"],
                "warehouse_id": 1,
                "inventory_state": "RAW",
                "movement_type": "TRANSFER",
                "reference_type": "PROCESSING_JOB",
                "reference_id": job_id,
                "reference_number": job["processing_number"],
                "quantity_change": -qty,
                "weight_change": -wt,
                "performed_by": performed_by,
                "remarks": f"Reserving stock for {job['processing_number']}",
            }, conn)
            
            # Add to RESERVED
            _validate_movement(item["material_id"], "RESERVED", "TRANSFER", qty, wt, conn)
            inventory_repository.apply_movement({
                "movement_key": f"START_RES:{job_id}:{item['id']}",
                "material_id": item["material_id"],
                "warehouse_id": 1,
                "inventory_state": "RESERVED",
                "movement_type": "TRANSFER",
                "reference_type": "PROCESSING_JOB",
                "reference_id": job_id,
                "reference_number": job["processing_number"],
                "quantity_change": qty,
                "weight_change": wt,
                "performed_by": performed_by,
                "remarks": f"Reserved stock for {job['processing_number']}",
            }, conn)
            
        processing_repository.log_job_activity(job_id, "IN_PROGRESS", performed_by, "Job started and inventory reserved.", conn)
        from repositories.activity_log_repository import log_activity
        log_activity(performed_by, "Processing Started", f"Started processing job {job['processing_number']}", module="Processing", reference_number=job["processing_number"], conn=conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def complete_job(job_id, outputs, losses, performed_by):
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        job = processing_repository.get_processing_job(job_id)
        if not job:
            raise ValueError("Processing job not found.")
        if job["status"] != "IN_PROGRESS":
            raise ValueError("Only jobs in progress can be completed.")
            
        # 1. Calculate and validate weight balance
        total_input_weight = sum(float(item["weight"]) for item in job["inputs"])
        total_output_weight = sum(float(item.get("weight", 0)) for item in outputs)
        total_loss_weight = sum(float(item.get("loss_weight", 0)) for item in losses)
        
        diff = abs(total_input_weight - (total_output_weight + total_loss_weight))
        if diff > PROCESSING_WEIGHT_TOLERANCE + 0.00001:
            raise ValueError(f"Weight balance check failed. Input weight ({total_input_weight:.2f} kg) must equal output + loss weight ({total_output_weight + total_loss_weight:.2f} kg) within +/- {PROCESSING_WEIGHT_TOLERANCE} kg tolerance. Difference: {diff:.2f} kg.")
            
        # 2. Save outputs and losses
        processing_repository.save_outputs(job_id, outputs, conn)
        processing_repository.save_processing_loss(job_id, losses, conn)

        # Collect parent batch info from inputs (first available batch)
        parent_batch_id = None
        parent_batch_number = None
        for inp in job["inputs"]:
            existing_b = conn.execute(
                "SELECT id, batch_number FROM material_batch WHERE purchase_invoice_id = (SELECT purchase_invoice_id FROM purchase_invoice_item WHERE id = ?) AND material_id = ? LIMIT 1",
                (inp.get("purchase_invoice_item_id"), inp["material_id"])
            ).fetchone()
            if not existing_b:
                # Fallback: lookup batch by movement reference
                b_row = conn.execute(
                    "SELECT batch_id, batch_number FROM stock_movement WHERE reference_type = 'PURCHASE' AND material_id = ? AND batch_id IS NOT NULL ORDER BY id DESC LIMIT 1",
                    (inp["material_id"],)
                ).fetchone()
                if b_row and b_row[0]:
                    parent_batch_id = b_row[0]
                    parent_batch_number = b_row[1]
            else:
                parent_batch_id = existing_b[0]
                parent_batch_number = existing_b[1]
            if parent_batch_id:
                break

        # 3. Consume RESERVED inventory
        for item in job["inputs"]:
            qty = float(item["quantity"])
            wt = float(item["weight"])
            op_type = item["processing_type"]

            _validate_movement(item["material_id"], "RESERVED", op_type, -qty, -wt, conn)
            inventory_repository.apply_movement({
                "movement_key": f"COMP_RAW:{job_id}:{item['id']}",
                "material_id": item["material_id"],
                "warehouse_id": 1,
                "inventory_state": "RESERVED",
                "movement_type": op_type,
                "reference_type": "PROCESSING_JOB",
                "reference_id": job_id,
                "reference_number": job["processing_number"],
                "batch_id": parent_batch_id,
                "batch_number": parent_batch_number,
                "quantity_change": -qty,
                "weight_change": -wt,
                "performed_by": performed_by,
                "remarks": f"Consumed reserved stock in job {job['processing_number']} ({op_type})",
            }, conn)
            
        # 4. Add outputs to inventory (target state) & Disposal Queue
        from repositories import disposal_repository, material_repository

        for idx, item in enumerate(outputs):
            qty = float(item.get("quantity", 0))
            wt = float(item.get("weight", 0))
            category = item.get("output_category", "RECOVERABLE")

            # Assign default state based on category if state is RAW/default
            raw_state = item.get("inventory_state", "RAW")
            if raw_state == "RAW":
                if category == "RECOVERABLE":
                    state = "RECOVERED"
                elif category == "REFURBISHABLE":
                    state = "FINISHED"
                elif category == "DISPOSAL":
                    state = "DISPOSED"
                else:
                    state = "RECOVERED"
            else:
                state = raw_state

            _validate_movement(item["material_id"], state, "PROCESSING", qty, wt, conn)
            inventory_repository.apply_movement({
                "movement_key": f"COMP_OUT:{job_id}:{idx}",
                "material_id": item["material_id"],
                "warehouse_id": 1,
                "inventory_state": state,
                "movement_type": "PROCESSING",
                "reference_type": "PROCESSING_JOB",
                "reference_id": job_id,
                "reference_number": job["processing_number"],
                "batch_id": parent_batch_id,
                "batch_number": parent_batch_number,
                "quantity_change": qty,
                "weight_change": wt,
                "performed_by": performed_by,
                "remarks": f"{category.capitalize()} material output from job {job['processing_number']}",
            }, conn)

            # Update processing_output with parent batch
            conn.execute(
                """UPDATE processing_output SET parent_batch_id = ?, parent_batch_number = ?
                   WHERE processing_job_id = ? AND material_id = ? AND output_category = ? AND rowid = (
                       SELECT rowid FROM processing_output WHERE processing_job_id = ? AND material_id = ? AND output_category = ? ORDER BY id DESC LIMIT 1
                   )""",
                (parent_batch_id, parent_batch_number, job_id, item["material_id"], category, job_id, item["material_id"], category)
            )

            # If output stream is DISPOSAL, automatically add to Disposal Queue with parent batch
            if category == "DISPOSAL":
                mat_info = material_repository.get_material_by_id(item["material_id"])
                mat_name = mat_info["material_name"] if mat_info else "Disposal Waste"
                unit = item.get("unit") or (mat_info["uom"] if mat_info else "KGS")

                disposal_repository.add_to_disposal_queue(
                    job_id=job_id,
                    job_number=job["processing_number"],
                    material_id=item["material_id"],
                    material_name=mat_name,
                    quantity=qty,
                    weight=wt,
                    unit=unit,
                    generated_date=job["processing_date"],
                    parent_batch_id=parent_batch_id,
                    parent_batch_number=parent_batch_number,
                    conn=conn
                )
                from repositories.activity_log_repository import log_activity
                log_activity(
                    performed_by,
                    "Disposal Queue Entry Created",
                    f"Added {wt} {unit} of {mat_name} from job {job['processing_number']} to Disposal Queue",
                    module="Processing",
                    reference_number=job["processing_number"],
                    conn=conn
                )

        # 5. Update status to COMPLETED
        job_data = {
            "processing_date": job["processing_date"],
            "status": "COMPLETED",
            "priority": job["priority"],
            "operator_id": job["operator_id"],
            "remarks": job["remarks"],
        }
        processing_repository.update_processing_job(job_id, job_data, conn)

        processing_repository.log_job_activity(job_id, "COMPLETED", performed_by, "Job completed, outputs classified, disposal queue updated.", conn)
        from repositories.activity_log_repository import log_activity
        log_activity(performed_by, "Processing Completed", f"Completed processing job {job['processing_number']}", module="Processing", reference_number=job["processing_number"], conn=conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def cancel_job(job_id, performed_by):
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        job = processing_repository.get_processing_job(job_id)
        if not job:
            raise ValueError("Processing job not found.")
        if job["status"] not in ("DRAFT", "READY", "IN_PROGRESS"):
            raise ValueError("Job cannot be cancelled in its current state.")
            
        # If the job was IN_PROGRESS, we must revert/release the reserved inventory
        if job["status"] == "IN_PROGRESS":
            for item in job["inputs"]:
                qty = float(item["quantity"])
                wt = float(item["weight"])
                
                # Revert: Subtract from RESERVED
                _validate_movement(item["material_id"], "RESERVED", "TRANSFER", -qty, -wt, conn)
                inventory_repository.apply_movement({
                    "movement_key": f"CANCEL_RES:{job_id}:{item['id']}",
                    "material_id": item["material_id"],
                    "warehouse_id": 1,
                    "inventory_state": "RESERVED",
                    "movement_type": "TRANSFER",
                    "reference_type": "PROCESSING_JOB",
                    "reference_id": job_id,
                    "reference_number": job["processing_number"],
                    "quantity_change": -qty,
                    "weight_change": -wt,
                    "performed_by": performed_by,
                    "remarks": f"Releasing reserved stock due to cancellation of {job['processing_number']}",
                }, conn)
                
                # Revert: Add back to RAW
                _validate_movement(item["material_id"], "RAW", "TRANSFER", qty, wt, conn)
                inventory_repository.apply_movement({
                    "movement_key": f"CANCEL_RAW:{job_id}:{item['id']}",
                    "material_id": item["material_id"],
                    "warehouse_id": 1,
                    "inventory_state": "RAW",
                    "movement_type": "TRANSFER",
                    "reference_type": "PROCESSING_JOB",
                    "reference_id": job_id,
                    "reference_number": job["processing_number"],
                    "quantity_change": qty,
                    "weight_change": wt,
                    "performed_by": performed_by,
                    "remarks": f"Released reserved stock back to RAW for {job['processing_number']}",
                }, conn)
                
        # Update status to CANCELLED
        job_data = {
            "processing_date": job["processing_date"],
            "status": "CANCELLED",
            "priority": job["priority"],
            "operator_id": job["operator_id"],
            "remarks": job["remarks"],
        }
        processing_repository.update_processing_job(job_id, job_data, conn)
        
        processing_repository.log_job_activity(job_id, "CANCELLED", performed_by, "Job cancelled and inventory reservation released.", conn)
        from repositories.activity_log_repository import log_activity
        log_activity(performed_by, "Processing Cancelled", f"Cancelled processing job {job['processing_number']}", module="Processing", reference_number=job["processing_number"], conn=conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def reopen_job(job_id, performed_by, user_role):
    if user_role != "admin":
        raise ValueError("Only Super Admin or Admin role can reopen a completed job.")
        
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        job = processing_repository.get_processing_job(job_id)
        if not job:
            raise ValueError("Processing job not found.")
        if job["status"] != "COMPLETED":
            raise ValueError("Only completed jobs can be reopened.")
            
        # 1. Reverse outputs from inventory (subtract them)
        for idx, item in enumerate(job["outputs"]):
            qty = float(item["quantity"])
            wt = float(item["weight"])
            state = item["inventory_state"]
            
            _validate_movement(item["material_id"], state, "PROCESSING", -qty, -wt, conn)
            inventory_repository.apply_movement({
                "movement_key": f"REOPEN_OUT:{job_id}:{idx}",
                "material_id": item["material_id"],
                "warehouse_id": 1,
                "inventory_state": state,
                "movement_type": "PROCESSING",
                "reference_type": "PROCESSING_JOB",
                "reference_id": job_id,
                "reference_number": job["processing_number"],
                "quantity_change": -qty,
                "weight_change": -wt,
                "performed_by": performed_by,
                "remarks": f"Reversing material output due to reopening of {job['processing_number']}",
            }, conn)
            
        # 2. Put inputs back into RESERVED (add them)
        for item in job["inputs"]:
            qty = float(item["quantity"])
            wt = float(item["weight"])
            op_type = item["processing_type"]
            
            _validate_movement(item["material_id"], "RESERVED", op_type, qty, wt, conn)
            inventory_repository.apply_movement({
                "movement_key": f"REOPEN_RAW:{job_id}:{item['id']}",
                "material_id": item["material_id"],
                "warehouse_id": 1,
                "inventory_state": "RESERVED",
                "movement_type": op_type,
                "reference_type": "PROCESSING_JOB",
                "reference_id": job_id,
                "reference_number": job["processing_number"],
                "quantity_change": qty,
                "weight_change": wt,
                "performed_by": performed_by,
                "remarks": f"Restoring consumed raw stock to reserved state for reopening of {job['processing_number']}",
            }, conn)
            
        # 3. Update status to IN_PROGRESS
        job_data = {
            "processing_date": job["processing_date"],
            "status": "IN_PROGRESS",
            "priority": job["priority"],
            "operator_id": job["operator_id"],
            "remarks": job["remarks"],
        }
        processing_repository.update_processing_job(job_id, job_data, conn)
        
        processing_repository.log_job_activity(job_id, "IN_PROGRESS", performed_by, f"Job reopened by Admin {performed_by}. Inventory outputs reversed and inputs returned to reserved state.", conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def duplicate_job(job_id, performed_by):
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        job = processing_repository.get_processing_job(job_id)
        if not job:
            raise ValueError("Processing job not found.")
            
        # Create a new draft job
        new_job_data = {
            "processing_number": generate_job_number(conn),
            "processing_date": date.today().strftime("%Y-%m-%d"),
            "status": "DRAFT",
            "priority": job["priority"],
            "operator_id": performed_by,
            "remarks": f"Duplicated from {job['processing_number']}. " + (job["remarks"] or ""),
        }
        
        new_job_id = processing_repository.create_processing_job(new_job_data, conn)
        
        # Duplicate Inputs
        inputs = [{
            "material_id": item["material_id"],
            "quantity": item["quantity"],
            "weight": item["weight"],
            "unit": item["unit"],
            "processing_type": item["processing_type"],
            "inventory_reference": item["inventory_reference"],
        } for item in job["inputs"]]
        processing_repository.save_inputs(new_job_id, inputs, conn)
        
        # Duplicate Outputs
        outputs = [{
            "material_id": item["material_id"],
            "quantity": item["quantity"],
            "weight": item["weight"],
            "unit": item["unit"],
            "inventory_state": item["inventory_state"],
            "recovered_from_material_id": item["recovered_from_material_id"],
        } for item in job["outputs"]]
        processing_repository.save_outputs(new_job_id, outputs, conn)
        
        # Duplicate Losses
        losses = [{
            "loss_weight": item["loss_weight"],
            "loss_reason": item["loss_reason"],
            "remarks": item["remarks"],
        } for item in job["losses"]]
        processing_repository.save_processing_loss(new_job_id, losses, conn)
        
        processing_repository.log_job_activity(new_job_id, "DRAFT", performed_by, f"Job duplicated from {job['processing_number']}.", conn)
        conn.commit()
        return new_job_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
