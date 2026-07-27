import os
import re
import hashlib
import logging
from datetime import datetime, date
from uuid import uuid4
from database import get_connection
from repositories import certificate_repository, party_repository
from services import certificate_pdf_service

logger = logging.getLogger(__name__)

# Ensure certificates storage directory exists
STORAGE_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "static", "certificates"))
os.makedirs(STORAGE_DIR, exist_ok=True)

def generate_certificate_number(conn=None):
    from repositories import settings_repository
    return settings_repository.increment_and_get_number("CERTIFICATE", conn)

def sanitize_filename(name):
    clean = re.sub(r'[^A-Za-z0-9_]', '_', name)
    clean = re.sub(r'_+', '_', clean).strip('_')
    return clean.upper()

def create_draft_certificate(customer_id, cert_type, template_key, job_ids, purchase_ids, remarks, performed_by, template_json=None, custom_table_json=None):
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        cursor = conn.cursor()
        
        # 1. Validate Customer
        cursor.execute("SELECT id, company_name FROM party WHERE id = ?", (customer_id,))
        p_row = cursor.fetchone()
        if not p_row:
            raise ValueError("Invalid Customer selected.")
        customer_name = p_row[1]
        
        # Resolve purchase_id: support legacy lists or new single purchase reference
        purchase_id = None
        if purchase_ids:
            purchase_id = purchase_ids[0]
            
        # 2. Check duplicate certificate prevention
        if purchase_id:
            cursor.execute(
                """SELECT certificate_number FROM certificate 
                   WHERE purchase_id = ? AND status NOT IN ('CANCELLED', 'SUPERSEDED') LIMIT 1""",
                (purchase_id,)
            )
            cert_exists = cursor.fetchone()
            if cert_exists:
                raise ValueError(f"Selected Purchase Invoice is already certified in certificate {cert_exists[0]}. Cancel or supersede it first.")

        # Get latest active template details from versioned table
        cursor.execute("SELECT version, template_json FROM document_template WHERE template_key = ? ORDER BY version DESC LIMIT 1", (template_key,))
        t_row = cursor.fetchone()
        t_ver = t_row[0] if t_row else 1
        t_json = template_json or (t_row[1] if t_row else None)
        
        cert_data = {
            "certificate_number": generate_certificate_number(conn),
            "certificate_type": cert_type,
            "customer_id": customer_id,
            "status": "DRAFT",
            "template_key": template_key,
            "template_version": t_ver,
            "generation_date": None,
            "version_number": 1,
            "verification_uuid": str(uuid4()),
            "remarks": remarks,
            "purchase_id": purchase_id,
            "template_json": t_json,
            "custom_table_json": custom_table_json
        }
        
        cert_id = certificate_repository.create_certificate(cert_data, conn)
        
        # Keep legacy relationship tables populated for compatibility
        if purchase_id:
            certificate_repository.link_purchase(cert_id, purchase_id, conn)
        for job_id in (job_ids or []):
            certificate_repository.link_processing_job(cert_id, job_id, conn)
            
        certificate_repository.save_certificate_activity(cert_id, "CREATED", performed_by, "Certificate draft prepared.", conn)
        
        # Unified audit log
        from document_engine.repositories.document_repository import insert_audit_log
        insert_audit_log(
            user_name=performed_by,
            action="CERTIFICATE_CREATED",
            entity_type="certificate",
            entity_id=cert_data["certificate_number"],
            new_version=1,
            details=f"Created certificate draft {cert_data['certificate_number']}",
            conn=conn
        )
        
        from repositories.activity_log_repository import log_activity
        log_activity(performed_by, "Create Certificate Draft", f"Created certificate draft {cert_data['certificate_number']}", module="Certificates", reference_number=cert_data['certificate_number'], conn=conn)
        conn.commit()
        return cert_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def generate_and_lock_certificate(cert_id, performed_by):
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        
        cert = certificate_repository.get_certificate(cert_id, conn)
        if not cert:
            raise ValueError("Certificate not found.")
        if cert["status"] not in ("DRAFT", "PREVIEW"):
            raise ValueError("Only draft or preview certificates can be generated.")
            
        # 1. Update status to LOCKED & set date
        gen_date = date.today().strftime("%Y-%m-%d")
        
        # Populate locked context
        cert["status"] = "LOCKED"
        cert["generation_date"] = gen_date
        
        # 2. Render PDF bytes using new document_engine to populate transient render cache
        from document_engine.services.document_service import render_document
        # Build complete rendering context compatible with document_engine
        from repositories import company_repository
        company_row = company_repository.get_company()
        company = dict(company_row) if company_row else {}
        
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM party WHERE id = ?", (cert["customer_id"],))
        party_row = cursor.fetchone()
        party = dict(party_row) if party_row else {}
        
        purchase = {}
        if cert.get("purchase_id"):
            cursor.execute("SELECT * FROM purchase_invoice WHERE id = ?", (cert["purchase_id"],))
            pur_row = cursor.fetchone()
            purchase = dict(pur_row) if pur_row else {}
            
        render_context = {
            "company": company,
            "party": party,
            "purchase": purchase,
            "document": cert,
            "template": cert["template"],
            "materials": cert["materials"],
            "custom_table_json": cert.get("custom_table_json"),
            "document_number": cert["certificate_number"],
            "status": "LOCKED",
            "generation_date": gen_date
        }
        
        pdf_bytes = render_document(render_context, user_role="user", performed_by=performed_by, conn=conn)
        checksum = hashlib.sha256(pdf_bytes).hexdigest()
        
        # 3. Save PDF metadata in DB (No physical file written to disk, complying with Storage Strategy)
        pdf_data = {
            "certificate_id": cert_id,
            "pdf_path": f"/certificates/download/{cert_id}",  # Decoupled download endpoint route
            "version": cert["version_number"],
            "generated_by": performed_by,
            "checksum": checksum,
            "status": "ACTIVE"
        }
        certificate_repository.save_pdf_version(pdf_data, conn)
        
        # 4. Update header record
        cursor.execute(
            "UPDATE certificate SET status = 'LOCKED', generation_date = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (gen_date, cert_id)
        )
        
        certificate_repository.save_certificate_activity(cert_id, "LOCKED", performed_by, "Official PDF generated and locked (metadata saved).", conn)
        
        # Unified audit log
        from document_engine.repositories.document_repository import insert_audit_log
        insert_audit_log(
            user_name=performed_by,
            action="DOCUMENT_GENERATED",
            entity_type="certificate",
            entity_id=cert["certificate_number"],
            new_version=cert["version_number"],
            details=f"Locked and generated PDF metadata for certificate {cert['certificate_number']}",
            conn=conn
        )
        
        from repositories.activity_log_repository import log_activity
        log_activity(performed_by, "Lock Certificate", f"Locked and generated PDF for certificate {cert['certificate_number']}", module="Certificates", reference_number=cert['certificate_number'], conn=conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def cancel_certificate(cert_id, reason, performed_by):
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        
        cert = certificate_repository.get_certificate(cert_id)
        if not cert:
            raise ValueError("Certificate not found.")
        if cert["status"] == "CANCELLED":
            raise ValueError("Certificate is already cancelled.")
            
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE certificate
               SET status = 'CANCELLED', cancellation_reason = ?, cancelled_by = ?, cancelled_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (reason, performed_by, cert_id)
        )
        
        certificate_repository.save_certificate_activity(cert_id, "CANCELLED", performed_by, f"Certificate cancelled. Reason: {reason}", conn)
        
        # Unified audit log
        from document_engine.repositories.document_repository import insert_audit_log
        insert_audit_log(
            user_name=performed_by,
            action="CERTIFICATE_CANCELLED",
            entity_type="certificate",
            entity_id=cert["certificate_number"],
            details=f"Cancelled certificate. Reason: {reason}",
            conn=conn
        )
        
        from repositories.activity_log_repository import log_activity
        log_activity(performed_by, "Cancel Certificate", f"Cancelled certificate {cert['certificate_number']}. Reason: {reason}", module="Certificates", reference_number=cert['certificate_number'], conn=conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def supersede_certificate(cert_id, template_key, remarks, performed_by):
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        
        old_cert = certificate_repository.get_certificate(cert_id, conn)
        if not old_cert:
            raise ValueError("Original certificate not found.")
        if old_cert["status"] not in ("GENERATED", "LOCKED"):
            raise ValueError("Only active locked certificates can be superseded.")
            
        # Create new replacement certificate
        new_number = generate_certificate_number(conn)
        new_version_num = old_cert["version_number"] + 1
        
        cursor = conn.cursor()
        cursor.execute("SELECT version, template_json FROM document_template WHERE template_key = ? ORDER BY version DESC LIMIT 1", (template_key,))
        t_row = cursor.fetchone()
        t_ver = t_row[0] if t_row else 1
        t_json = t_row[1] if t_row else None
        
        # Insert replacement record
        new_cert_data = {
            "certificate_number": new_number,
            "certificate_type": old_cert["certificate_type"],
            "customer_id": old_cert["customer_id"],
            "status": "LOCKED",
            "template_key": template_key,
            "template_version": t_ver,
            "generation_date": date.today().strftime("%Y-%m-%d"),
            "version_number": new_version_num,
            "superseded_certificate_id": None,
            "replaces_certificate_id": old_cert["id"],
            "verification_uuid": str(uuid4()),
            "remarks": f"Replaces superseded certificate {old_cert['certificate_number']}. " + (remarks or ""),
            "purchase_id": old_cert.get("purchase_id"),
            "template_json": t_json or old_cert.get("template_json"),
            "custom_table_json": old_cert.get("custom_table_json")
        }
        
        new_id = certificate_repository.create_certificate(new_cert_data, conn)
        
        # Link same completed jobs and purchases
        for job in old_cert["processing_jobs"]:
            certificate_repository.link_processing_job(new_id, job["processing_job_id"], conn)
        for p in old_cert["purchases"]:
            certificate_repository.link_purchase(new_id, p["purchase_id"], conn)
            
        # Copy asset attachments if any exist
        for att in old_cert["attachments"]:
            cursor.execute(
                """INSERT INTO certificate_asset_attachment (certificate_id, file_name, file_path, file_type, uploaded_by)
                   VALUES (?, ?, ?, ?, ?)""",
                (new_id, att["file_name"], att["file_path"], att["file_type"], performed_by)
            )
            
        # Render the PDF for the replacement certificate using new document_engine to populate cache
        new_cert = certificate_repository.get_certificate(new_id, conn)
        
        from document_engine.services.document_service import render_document
        from repositories import company_repository
        company_row = company_repository.get_company()
        company = dict(company_row) if company_row else {}
        
        cursor.execute("SELECT * FROM party WHERE id = ?", (new_cert["customer_id"],))
        party_row = cursor.fetchone()
        party = dict(party_row) if party_row else {}
        
        purchase = {}
        if new_cert.get("purchase_id"):
            cursor.execute("SELECT * FROM purchase_invoice WHERE id = ?", (new_cert["purchase_id"],))
            pur_row = cursor.fetchone()
            purchase = dict(pur_row) if pur_row else {}
            
        render_context = {
            "company": company,
            "party": party,
            "purchase": purchase,
            "document": new_cert,
            "template": new_cert["template"],
            "materials": new_cert["materials"],
            "custom_table_json": new_cert.get("custom_table_json"),
            "document_number": new_cert["certificate_number"],
            "status": "LOCKED",
            "generation_date": new_cert["generation_date"]
        }
        
        pdf_bytes = render_document(render_context, user_role="user", performed_by=performed_by, conn=conn)
        checksum = hashlib.sha256(pdf_bytes).hexdigest()
        
        # Save PDF path (no physical file written)
        pdf_data = {
            "certificate_id": new_id,
            "pdf_path": f"/certificates/download/{new_id}",
            "version": new_version_num,
            "generated_by": performed_by,
            "checksum": checksum,
            "status": "ACTIVE"
        }
        certificate_repository.save_pdf_version(pdf_data, conn)
        
        # Update old certificate status to SUPERSEDED
        cursor.execute(
            "UPDATE certificate SET status = 'SUPERSEDED', superseded_certificate_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (new_id, cert_id)
        )
        
        certificate_repository.save_certificate_activity(cert_id, "SUPERSEDED", performed_by, f"Superseded by replacement certificate {new_number}", conn)
        certificate_repository.save_certificate_activity(new_id, "CREATED", performed_by, f"Replacement certificate generated for superseded {old_cert['certificate_number']}", conn)
        
        # Unified audit logs
        from document_engine.repositories.document_repository import insert_audit_log
        insert_audit_log(
            user_name=performed_by,
            action="CERTIFICATE_SUPERSEDED",
            entity_type="certificate",
            entity_id=old_cert["certificate_number"],
            previous_version=old_cert["version_number"],
            new_version=new_version_num,
            details=f"Superseded by replacement certificate {new_number}",
            conn=conn
        )
        insert_audit_log(
            user_name=performed_by,
            action="CERTIFICATE_CREATED",
            entity_type="certificate",
            entity_id=new_number,
            new_version=new_version_num,
            details=f"Created replacement certificate {new_number} for superseded {old_cert['certificate_number']}",
            conn=conn
        )
        
        from repositories.activity_log_repository import log_activity
        log_activity(performed_by, "Supersede Certificate", f"Superseded certificate {old_cert['certificate_number']} with {new_number}", module="Certificates", reference_number=new_number, conn=conn)
        conn.commit()
        return new_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def batch_generate_certificates(job_ids, template_key, performed_by, mode="CONSOLIDATED"):
    """
    Batch Generation Engine (5.21)
    """
    if not job_ids:
        raise ValueError("No Processing Jobs selected.")
        
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # Trace customer IDs for selected jobs
        placeholders = ",".join("?" for _ in job_ids)
        cursor.execute(
            f"""SELECT DISTINCT pj.id,
                       (SELECT DISTINCT pi.supplier_id
                        FROM processing_input pin
                        JOIN purchase_invoice pi ON pi.purchase_invoice_number = pin.inventory_reference OR pi.id = pin.inventory_reference
                        WHERE pin.processing_job_id = pj.id AND pi.is_active = 1
                        LIMIT 1) AS customer_id
                FROM processing_job pj
                WHERE pj.id IN ({placeholders})""",
            job_ids
        )
        job_map = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Verify cross-customer links are valid
        cust_ids = set(job_map.values())
        if None in cust_ids or not cust_ids:
            raise ValueError("Could not resolve Customer references for one or more selected jobs.")
            
        if mode == "CONSOLIDATED":
            if len(cust_ids) > 1:
                raise ValueError("Consolidated certificates can only be generated for jobs belonging to a single customer.")
            customer_id = list(cust_ids)[0]
            
            # Resolve purchase ID link for consolidated
            cursor.execute(
                f"""SELECT DISTINCT pi.id
                    FROM processing_input pin
                    JOIN purchase_invoice pi ON pi.purchase_invoice_number = pin.inventory_reference OR pi.id = pin.inventory_reference
                    WHERE pin.processing_job_id IN ({placeholders}) AND pi.is_active = 1
                    LIMIT 1""",
                job_ids
            )
            pur_row = cursor.fetchone()
            purchase_ids = [pur_row[0]] if pur_row else []
            
            cert_id = create_draft_certificate(customer_id, "COMBINED", template_key, job_ids, purchase_ids, "Batch Consolidated", performed_by)
            generate_and_lock_certificate(cert_id, performed_by)
            return [cert_id]
        else:
            # Mode = INDIVIDUAL: generate separate certificates
            generated_ids = []
            for j_id in job_ids:
                cust_id = job_map[j_id]
                
                # Resolve purchase ID link
                cursor.execute(
                    """SELECT DISTINCT pi.id
                        FROM processing_input pin
                        JOIN purchase_invoice pi ON pi.purchase_invoice_number = pin.inventory_reference OR pi.id = pin.inventory_reference
                        WHERE pin.processing_job_id = ? AND pi.is_active = 1
                        LIMIT 1""",
                    (j_id,)
                )
                pur_row = cursor.fetchone()
                purchase_ids = [pur_row[0]] if pur_row else []
                
                cert_id = create_draft_certificate(cust_id, "RECYCLING", template_key, [j_id], purchase_ids, "Batch Individual", performed_by)
                generate_and_lock_certificate(cert_id, performed_by)
                generated_ids.append(cert_id)
            return generated_ids
    finally:
        conn.close()
