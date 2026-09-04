from flask import Response
from backend.pdf.pdf_generator import render_to_pdf as playwright_render_to_pdf
from backend.pdf.pdf_generator import compile_html_to_pdf as playwright_compile_html_to_pdf
from backend.pdf.pdf_generator import render_url_to_pdf as playwright_render_url_to_pdf

def render_to_pdf(template_name, context):
    """
    Renders a template with context and converts it to PDF bytes using Playwright.
    """
    # Use 0.5in margins on top/bottom, 0.6in on left/right for standard A4 layout
    margin = {"top": "0.5in", "bottom": "0.5in", "left": "0.6in", "right": "0.6in"}
    return playwright_render_to_pdf(template_name, context, margin=margin)

def compile_html_to_pdf(html_content):
    """
    Directly compiles any HTML content string to PDF bytes using Playwright.
    """
    margin = {"top": "0.5in", "bottom": "0.5in", "left": "0.6in", "right": "0.6in"}
    return playwright_compile_html_to_pdf(html_content, margin=margin)

def render_url_to_pdf(url, landscape=False):
    """
    Instructs Playwright to render a print endpoint URL directly to PDF.
    """
    return playwright_render_url_to_pdf(url, landscape=landscape)

def send_pdf_response(pdf_bytes, filename):
    """
    Returns a Flask Response object configured for a PDF attachment download.
    """
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": len(pdf_bytes),
        },
    )
