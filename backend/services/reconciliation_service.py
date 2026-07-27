import logging
from database import get_connection

logger = logging.getLogger(__name__)


def reconcile_processing_job(job_id):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT processing_number, status, processing_date FROM processing_job WHERE id = ?", (job_id,))
        job_row = cursor.fetchone()
        if not job_row:
            return {"status": "NOT_FOUND", "is_reconciled": False}

        processing_number = job_row["processing_number"]

        # 1. Total Input Weight
        cursor.execute("SELECT COALESCE(SUM(weight), 0) FROM processing_input WHERE processing_job_id = ?", (job_id,))
        total_input_weight = float(cursor.fetchone()[0] or 0.0)

        # 2. Recoverable Weight
        cursor.execute(
            """SELECT COALESCE(SUM(weight), 0) FROM processing_output
               WHERE processing_job_id = ? AND output_category = 'RECOVERABLE'""",
            (job_id,)
        )
        recoverable_weight = float(cursor.fetchone()[0] or 0.0)

        # 3. Refurbishable Weight
        cursor.execute(
            """SELECT COALESCE(SUM(weight), 0) FROM processing_output
               WHERE processing_job_id = ? AND output_category = 'REFURBISHABLE'""",
            (job_id,)
        )
        refurbishable_weight = float(cursor.fetchone()[0] or 0.0)

        # 4. Disposal Weight
        cursor.execute(
            """SELECT COALESCE(SUM(weight), 0) FROM processing_output
               WHERE processing_job_id = ? AND output_category = 'DISPOSAL'""",
            (job_id,)
        )
        disposal_weight = float(cursor.fetchone()[0] or 0.0)

        # 5. Loss Weight
        cursor.execute("SELECT COALESCE(SUM(loss_weight), 0) FROM processing_loss WHERE processing_job_id = ?", (job_id,))
        loss_weight = float(cursor.fetchone()[0] or 0.0)

        total_output_weight = recoverable_weight + refurbishable_weight + disposal_weight + loss_weight
        discrepancy = round(total_input_weight - total_output_weight, 4)

        is_reconciled = abs(discrepancy) <= 0.05

        return {
            "job_id": job_id,
            "processing_number": processing_number,
            "job_status": job_row["status"],
            "total_input_weight": total_input_weight,
            "recoverable_weight": recoverable_weight,
            "refurbishable_weight": refurbishable_weight,
            "disposal_weight": disposal_weight,
            "loss_weight": loss_weight,
            "total_output_weight": total_output_weight,
            "discrepancy": discrepancy,
            "is_reconciled": is_reconciled,
            "warning": None if is_reconciled else f"Discrepancy of {discrepancy} KG detected in Job {processing_number}!"
        }
    finally:
        conn.close()


def get_system_reconciliation_summary():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM processing_job WHERE status = 'COMPLETED'")
        job_ids = [row[0] for row in cursor.fetchall()]

        reconciled_count = 0
        unreconciled_count = 0
        total_input = 0.0
        total_recoverable = 0.0
        total_refurbishable = 0.0
        total_disposal = 0.0
        total_loss = 0.0

        for jid in job_ids:
            res = reconcile_processing_job(jid)
            total_input += res["total_input_weight"]
            total_recoverable += res["recoverable_weight"]
            total_refurbishable += res["refurbishable_weight"]
            total_disposal += res["disposal_weight"]
            total_loss += res["loss_weight"]

            if res["is_reconciled"]:
                reconciled_count += 1
            else:
                unreconciled_count += 1

        overall_discrepancy = round(total_input - (total_recoverable + total_refurbishable + total_disposal + total_loss), 4)

        return {
            "completed_jobs_count": len(job_ids),
            "reconciled_jobs_count": reconciled_count,
            "unreconciled_jobs_count": unreconciled_count,
            "total_input_weight": total_input,
            "total_recoverable_weight": total_recoverable,
            "total_refurbishable_weight": total_refurbishable,
            "total_disposal_weight": total_disposal,
            "total_loss_weight": total_loss,
            "overall_discrepancy": overall_discrepancy,
            "is_fully_reconciled": unreconciled_count == 0 and abs(overall_discrepancy) <= 0.05
        }
    finally:
        conn.close()
