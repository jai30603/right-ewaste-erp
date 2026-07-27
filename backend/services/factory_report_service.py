import os
import uuid
import datetime
from pathlib import Path
from repositories import factory_report_repository
from services.factory_report_validator import FactoryReportValidationService
from document_engine.factory_report_generator import FactoryReportGenerator
from repositories.activity_log_repository import log_activity
from erp_platform.events.event_bus import event_bus, ErpEvent

REPORTS_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "static" / "uploads" / "factory_reports"


class FactoryReportService:

    @staticmethod
    def generate_factory_report(report_date, user_name="System"):
        # 1. Validation Engine
        is_valid, errors, warnings = FactoryReportValidationService.validate_generation_prerequisites(report_date)
        if not is_valid:
            return None, errors, warnings

        # 2. ERP Data Aggregation
        erp_data = factory_report_repository.get_erp_data_for_report(report_date)

        # 3. Output Path Setup
        REPORTS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        unique_filename = f"Factory_Report_{report_date}_{uuid.uuid4().hex[:8]}.xlsx"
        output_file_path = REPORTS_OUTPUT_DIR / unique_filename

        # 4. Document Engine Workbook Generation
        generator = FactoryReportGenerator()
        generator.generate(erp_data, output_file_path)

        file_size = output_file_path.stat().st_size if output_file_path.exists() else 0
        rel_file_path = f"/static/uploads/factory_reports/{unique_filename}"

        # 5. Report History Storage
        history_data = {
            "report_date": report_date,
            "template_version": "v1.0",
            "file_path": rel_file_path,
            "file_name": unique_filename,
            "file_size": file_size,
            "generated_by": user_name,
            "status": "Generated",
            "metadata": {
                "incoming_count": len(erp_data.get("incoming_materials", [])),
                "outgoing_count": len(erp_data.get("outgoing_materials", []))
            }
        }
        report_id = factory_report_repository.save_report_history(history_data)

        # 6. Audit & Activity Logging
        log_activity(
            user_name=user_name,
            action="Factory Report Generated",
            details=f"Generated Factory Daily Report workbook for date '{report_date}'.",
            module="FactoryReport",
            reference_number=f"FR-{report_id}"
        )

        event_bus.publish(ErpEvent(
            event_type="Factory Report Generated",
            source_module="FactoryReport",
            payload={"report_id": report_id, "report_date": report_date, "file_path": rel_file_path},
            user_name=user_name
        ))

        return report_id, [], warnings

    @staticmethod
    def get_report_history(limit=50):
        return factory_report_repository.get_report_history(limit=limit)

    @staticmethod
    def get_report_by_id(report_id):
        return factory_report_repository.get_report_by_id(report_id)

    @staticmethod
    def regenerate_report(report_id, user_name="System"):
        old_report = factory_report_repository.get_report_by_id(report_id)
        if not old_report:
            return None, ["Report history record not found."], []

        rep_date = old_report["report_date"]
        new_report_id, errors, warnings = FactoryReportService.generate_factory_report(rep_date, user_name=user_name)

        if new_report_id:
            log_activity(
                user_name=user_name,
                action="Factory Report Regenerated",
                details=f"Regenerated Factory Daily Report for date '{rep_date}'.",
                module="FactoryReport",
                reference_number=f"FR-{new_report_id}"
            )

        return new_report_id, errors, warnings
