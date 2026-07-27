import logging
import datetime
from database import get_connection
from services.reconciliation_service import get_system_reconciliation_summary

logger = logging.getLogger(__name__)


class ProductionReportEngine:

    @staticmethod
    def generate_daily_production_summary(report_date=None):
        if not report_date:
            report_date = datetime.date.today().isoformat()

        conn = get_connection()
        try:
            cursor = conn.cursor()

            # Purchase Intake
            cursor.execute(
                """SELECT COALESCE(SUM(pii.quantity), 0), COALESCE(SUM(pii.weight), 0)
                   FROM purchase_invoice_item pii
                   JOIN purchase_invoice pi ON pii.purchase_invoice_id = pi.id
                   WHERE pi.invoice_date = ? AND pi.status NOT IN ('DRAFT', 'CANCELLED')""",
                (report_date,)
            )
            purch_row = cursor.fetchone()
            intake_qty, intake_wt = purch_row[0], float(purch_row[1] or 0.0)

            # Processing Output Breakdown
            cursor.execute(
                """SELECT po.output_category, COALESCE(SUM(po.weight), 0)
                   FROM processing_output po
                   JOIN processing_job pj ON po.processing_job_id = pj.id
                   WHERE pj.processing_date = ? AND pj.status = 'COMPLETED'
                   GROUP BY po.output_category""",
                (report_date,)
            )
            output_rows = cursor.fetchall()
            outputs_map = {row[0]: float(row[1] or 0.0) for row in output_rows}

            # Sales Dispatch
            cursor.execute(
                """SELECT COALESCE(SUM(sii.quantity), 0), COALESCE(SUM(sii.weight), 0)
                   FROM sales_invoice_item sii
                   JOIN sales_invoice s ON sii.sales_invoice_id = s.id
                   WHERE s.invoice_date = ? AND s.status NOT IN ('DRAFT', 'CANCELLED')""",
                (report_date,)
            )
            sales_row = cursor.fetchone()
            dispatch_qty, dispatch_wt = sales_row[0], float(sales_row[1] or 0.0)

            # Disposal Queue items
            cursor.execute(
                """SELECT COUNT(*), COALESCE(SUM(weight), 0)
                   FROM disposal_queue
                   WHERE generated_date = ?""",
                (report_date,)
            )
            disp_row = cursor.fetchone()
            disp_queue_cnt, disp_queue_wt = disp_row[0], float(disp_row[1] or 0.0)

            return {
                "report_date": report_date,
                "intake_qty": intake_qty,
                "intake_wt": intake_wt,
                "recoverable_wt": outputs_map.get("RECOVERABLE", 0.0),
                "refurbishable_wt": outputs_map.get("REFURBISHABLE", 0.0),
                "disposal_wt": outputs_map.get("DISPOSAL", 0.0),
                "dispatch_qty": dispatch_qty,
                "dispatch_wt": dispatch_wt,
                "disposal_queue_count": disp_queue_cnt,
                "disposal_queue_wt": disp_queue_wt
            }
        finally:
            conn.close()

    @staticmethod
    def generate_cpcb_environmental_return(year=None):
        if not year:
            year = datetime.date.today().year

        conn = get_connection()
        try:
            cursor = conn.cursor()
            start_date = f"{year}-01-01"
            end_date = f"{year}-12-31"

            # Total E-Waste Processed
            cursor.execute(
                """SELECT COALESCE(SUM(pi.weight), 0)
                   FROM processing_input pi
                   JOIN processing_job pj ON pi.processing_job_id = pj.id
                   WHERE pj.processing_date BETWEEN ? AND ? AND pj.status = 'COMPLETED'""",
                (start_date, end_date)
            )
            total_processed_wt = float(cursor.fetchone()[0] or 0.0)

            # Category Wise Breakdown
            cursor.execute(
                """SELECT m.category, COALESCE(SUM(po.weight), 0)
                   FROM processing_output po
                   JOIN material m ON po.material_id = m.id
                   JOIN processing_job pj ON po.processing_job_id = pj.id
                   WHERE pj.processing_date BETWEEN ? AND ? AND pj.status = 'COMPLETED'
                   GROUP BY m.category""",
                (start_date, end_date)
            )
            category_breakdown = {row[0] or "Uncategorized": float(row[1] or 0.0) for row in cursor.fetchall()}

            # Disposal Queue Summary
            cursor.execute(
                """SELECT material_name, SUM(weight)
                   FROM disposal_queue
                   WHERE generated_date BETWEEN ? AND ?
                   GROUP BY LOWER(material_name)""",
                (start_date, end_date)
            )
            disposal_breakdown = {row[0]: float(row[1] or 0.0) for row in cursor.fetchall()}

            reconciliation = get_system_reconciliation_summary()

            return {
                "reporting_year": year,
                "period": f"{start_date} to {end_date}",
                "total_e_waste_processed_kgs": total_processed_wt,
                "category_breakdown": category_breakdown,
                "disposal_breakdown": disposal_breakdown,
                "reconciliation_status": reconciliation
            }
        finally:
            conn.close()
