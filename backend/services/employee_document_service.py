import os
import uuid
from pathlib import Path
from repositories import employee_document_repository, employee_repository
from repositories.activity_log_repository import log_activity
from erp_platform.events.event_bus import event_bus, ErpEvent

DOCUMENTS_UPLOAD_FOLDER = Path(__file__).resolve().parent.parent / "static" / "uploads" / "documents"
ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png", "docx"}


class EmployeeDocumentService:

    @staticmethod
    def get_employee_documents(employee_id):
        return employee_document_repository.get_documents_by_employee_id(employee_id)

    @staticmethod
    def upload_document(employee_id, category, file, user_name="System"):
        if not file or not file.filename:
            return None, ["No file selected for upload."]

        ext = file.filename.rsplit(".", 1)[1].lower() if "." in file.filename else ""
        if ext not in ALLOWED_EXTENSIONS:
            return None, [f"Invalid file extension '.{ext}'. Supported formats: PDF, JPG, PNG, DOCX."]

        DOCUMENTS_UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
        unique_name = f"doc_{employee_id}_{uuid.uuid4().hex[:10]}.{ext}"
        dest_path = DOCUMENTS_UPLOAD_FOLDER / unique_name

        file.save(dest_path)
        file_size = dest_path.stat().st_size if dest_path.exists() else 0

        doc_data = {
            "employee_id": employee_id,
            "document_category": category,
            "document_name": file.filename,
            "file_path": f"/static/uploads/documents/{unique_name}",
            "file_size": file_size,
            "file_type": ext.upper(),
            "uploaded_by": user_name
        }

        doc_id = employee_document_repository.save_document(doc_data)
        emp = employee_repository.get_employee_by_id(employee_id)
        emp_name = emp.get("full_name") if emp else f"ID #{employee_id}"

        log_activity(
            user_name=user_name,
            action="Employee Document Uploaded",
            details=f"Uploaded '{category}' document '{file.filename}' for {emp_name}.",
            module="Employee",
            reference_number=f"DOC-{doc_id}"
        )

        event_bus.publish(ErpEvent(
            event_type="Employee Document Uploaded",
            source_module="Employee",
            payload={"doc_id": doc_id, "employee_id": employee_id, "category": category},
            user_name=user_name
        ))

        return doc_id, []

    @staticmethod
    def delete_document(doc_id, user_name="System"):
        doc = employee_document_repository.get_document_by_id(doc_id)
        if not doc:
            return False, "Document record not found."

        # Delete physical file
        rel_path = doc["file_path"].lstrip("/").replace("/", os.sep)
        full_path = Path(__file__).resolve().parent.parent / rel_path
        if full_path.exists():
            try:
                full_path.unlink()
            except Exception:
                pass

        employee_document_repository.delete_document(doc_id)
        emp_id = doc["employee_id"]

        log_activity(
            user_name=user_name,
            action="Employee Document Deleted",
            details=f"Deleted '{doc['document_category']}' document #{doc_id}.",
            module="Employee",
            reference_number=f"DOC-{doc_id}"
        )

        event_bus.publish(ErpEvent(
            event_type="Employee Document Deleted",
            source_module="Employee",
            payload={"doc_id": doc_id, "employee_id": emp_id},
            user_name=user_name
        ))

        return True, "Document deleted successfully."
