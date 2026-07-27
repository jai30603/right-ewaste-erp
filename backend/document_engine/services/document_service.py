from document_engine.cache import render_cache
from document_engine.renderers.html_renderer import render_layout_to_html
from document_engine.pdf.pdf_converter import convert_html_to_pdf
from document_engine.repositories import document_repository, template_repository
from document_engine.validators.document_validator import check_permission

def render_document(context, user_role="user", performed_by="System", conn=None):
    """
    Decoupled document rendering pipeline.
    Uses Template Configuration + Business Context data.
    Implements transient Render Cache.
    """
    # 1. Check permissions
    if not check_permission(user_role, "view"):
        raise PermissionError("Access denied to Document Engine.")
        
    template = context.get("template") or {}
    template_key = template.get("template_key", "STANDARD")
    template_ver = template.get("version", 1)
    
    purchase = context.get("purchase") or {}
    purchase_id = purchase.get("id", 0)
    
    template_json = template.get("template_json")
    custom_table_json = context.get("custom_table_json")
    
    # 2. Check Cache layer
    cache_key = render_cache.generate_key(
        template_key=template_key,
        template_version=template_ver,
        purchase_id=purchase_id,
        template_json=template_json,
        custom_table_json=custom_table_json
    )
    
    cached_pdf = render_cache.get(cache_key)
    if cached_pdf:
        # Cache Hit - Audit and return cached PDF
        document_repository.insert_audit_log(
            user_name=performed_by,
            action="DOCUMENT_GENERATED_CACHE",
            entity_type="document",
            entity_id=context.get("document_number", "N/A"),
            details="Cache hit: served rendered PDF from memory.",
            conn=conn
        )
        return cached_pdf
        
    # 3. Cache Miss - Render HTML
    html_content = render_layout_to_html(template_json, context)
    
    # 4. Generate PDF bytes
    pdf_bytes = convert_html_to_pdf(html_content)
    
    # 5. Save in cache
    render_cache.set_cache(cache_key, pdf_bytes)
    
    # Audit log generation
    document_repository.insert_audit_log(
        user_name=performed_by,
        action="DOCUMENT_GENERATED",
        entity_type="document",
        entity_id=context.get("document_number", "N/A"),
        details="Cache miss: rendered HTML and generated new PDF bytes.",
        conn=conn
    )
    
    return pdf_bytes
 
def audit_document_download(document_number, user_name, conn=None):
    """
    Audits when a PDF document is downloaded.
    """
    document_repository.insert_audit_log(
        user_name=user_name,
        action="DOCUMENT_DOWNLOADED",
        entity_type="document",
        entity_id=document_number,
        details="User downloaded PDF document.",
        conn=conn
    )
