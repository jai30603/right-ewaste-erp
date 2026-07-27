import datetime
from pathlib import Path

TEMPLATE_FILE = Path(__file__).resolve().parent.parent / "documents" / "templates" / "factory_report" / "factory_report_template.xlsx"
MAPPING_FILE = Path(__file__).resolve().parent.parent / "documents" / "templates" / "factory_report" / "factory_report_mapping.json"


class FactoryReportValidationService:

    @staticmethod
    def validate_generation_prerequisites(report_date_str):
        errors = []
        warnings = []

        # 1. Validate Date Format
        if not report_date_str:
            errors.append("Report Date is required.")
        else:
            try:
                dt = datetime.datetime.strptime(report_date_str, "%Y-%m-%d")
                if dt.date() > datetime.date.today():
                    warnings.append("Generating report for a future date.")
            except ValueError:
                errors.append("Invalid date format. Expected YYYY-MM-DD.")

        # 2. Validate Master Template File Existence
        if not TEMPLATE_FILE.exists():
            errors.append(f"Master template file missing at '{TEMPLATE_FILE.name}'.")

        # 3. Validate Mapping Config File Existence
        if not MAPPING_FILE.exists():
            errors.append(f"Mapping configuration file missing at '{MAPPING_FILE.name}'.")

        is_valid = len(errors) == 0
        return is_valid, errors, warnings
