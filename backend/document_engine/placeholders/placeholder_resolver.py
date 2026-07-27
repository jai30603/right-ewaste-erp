import re
from datetime import date

def get_standard_placeholders(context):
    """
    Builds the standard mapping for placeholders using context details.
    """
    company = context.get("company", {})
    party = context.get("party", {})
    purchase = context.get("purchase", {})
    document = context.get("document", {})
    
    # Base resolved placeholders
    mapping = {
        "COMPANY_NAME": company.get("company_name") or "Right Ewaste Recycle",
        "COMPANY_ADDRESS": f"{company.get('address_line_1', '')} {company.get('address_line_2', '')}, {company.get('city', '')}, {company.get('state', '')} - {company.get('pincode', '')}".strip().replace("  ", " "),
        
        "SUPPLIER_NAME": party.get("company_name") or party.get("contact_person") or "Valued Client",
        "SUPPLIER_ADDRESS": party.get("billing_address") or "N/A",
        
        "PURCHASE_NO": purchase.get("purchase_invoice_number") or "N/A",
        "PURCHASE_DATE": purchase.get("invoice_date") or "N/A",
        
        "CERTIFICATE_NO": document.get("certificate_number") or document.get("document_number") or "DRAFT-CERT",
        "DATE": document.get("generation_date") or date.today().strftime("%Y-%m-%d"),
        
        "DECLARATION": context.get("declaration") or document.get("declaration_text") or "Certified responsibly.",
        "SIGNATURE": document.get("signature_title") or "Authorized Signatory",
        "STAMP": "",      # Handled during plugin / image insertion
        "QR_CODE": "",    # Handled by QrPlugin
        "BARCODE": ""     # Handled by BarcodePlugin
    }
    
    return mapping

def resolve_placeholders(text, context):
    """
    Replaces all double curly braces placeholders in text.
    """
    if not text:
        return ""
        
    mapping = get_standard_placeholders(context)
    
    # Also support general keys in context
    for k, v in context.items():
        if k not in mapping and not isinstance(v, (dict, list)):
            mapping[k] = str(v) if v is not None else ""
            
    # Replacement function
    def replacer(match):
        key = match.group(1).strip()
        return str(mapping.get(key, match.group(0)))
        
    # Replace all {{KEY}}
    pattern = re.compile(r"\{\{([^}]+)\}\}")
    return pattern.sub(replacer, text)
