import os
from datetime import date
from services.pdf_service import render_to_pdf
from repositories import company_repository

def generate_pdf_bytes(cert):
    """
    Decoupled PDF Service
    Generates PDF bytes for the given certificate dictionary.
    """
    company_row = company_repository.get_company()
    company = dict(company_row) if company_row else {
        "company_name": "Right Ewaste Recycle",
        "address_line_1": "Factory Area, Sector 4",
        "address_line_2": "",
        "city": "Mumbai",
        "state": "Maharashtra",
        "state_code": "27",
        "pincode": "400001",
        "gstin": "27AAACR9999A1Z1",
        "pan": "AAACR9999A",
        "phone": "+91 98765 43210",
        "email": "info@rightewaste.com",
        "website": "www.rightewaste.com"
    }

    # Extract template layout variables
    template = cert.get("template") or {
        "title": "CERTIFICATE OF RECYCLING",
        "declaration_text": "This certifies that electronic waste has been responsibly processed.",
        "signature_title": "Authorized Signatory",
        "show_logo": 1,
        "show_customer_details": 1,
        "show_purchase_references": 1,
        "show_processing_summary": 1,
        "show_weight_summary": 1,
        "show_asset_list": 1,
        "show_gst": 1,
        "show_cin": 1,
        "show_pan": 1,
        "show_pcb": 1,
        "show_iso": 0,
        "show_r2": 0,
        "show_estewards": 0,
        "margin_top": 36.0,
        "margin_bottom": 36.0,
        "margin_left": 36.0,
        "margin_right": 36.0
    }

    # Calculate total weight and total quantity
    total_weight = sum(float(item.get("weight", 0)) for item in cert.get("materials", []))
    total_quantity = sum(float(item.get("quantity", 0)) for item in cert.get("materials", []))

    context = {
        "cert": cert,
        "company": company,
        "template": template,
        "total_weight": total_weight,
        "total_quantity": total_quantity,
        "generation_date": cert.get("generation_date") or date.today().strftime("%Y-%m-%d")
    }

    # Render ReportLab-compatible HTML to PDF
    pdf_bytes = render_to_pdf("reports/certificate_pdf.html", context)
    return pdf_bytes
