"""
PDF Service
Centralizes PDF generation from templates using xhtml2pdf.
"""
import io
import os
from urllib.parse import urlparse
from flask import render_template, Response
from xhtml2pdf import pisa
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Register custom fonts in ReportLab to avoid xhtml2pdf temporary file lock bugs on Windows
_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
_font_path = os.path.normpath(os.path.join(_root, 'static', 'fonts', 'SegoeUI.ttf'))
if os.path.exists(_font_path):
    pdfmetrics.registerFont(TTFont('Segoe UI', _font_path))

def _fetch_pdf_resource(uri, rel):
    """
    Callback function to resolve relative static paths for xhtml2pdf.
    """
    parsed = urlparse(uri)
    if parsed.scheme == 'file':
        path = parsed.path
        if path.startswith('/') and path[2:3] == ':':
            path = path[1:]
        return os.path.normpath(path)
    if uri.startswith('/static/'):
        # backend is at path parent of services folder
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        return os.path.normpath(os.path.join(root, uri.lstrip('/').replace('/', os.sep)))
    return uri

def render_to_pdf(template_name, context):
    """
    Renders a template with context and converts it to PDF bytes.
    """
    html = render_template(template_name, **context)
    buf = io.BytesIO()
    pisa.CreatePDF(io.StringIO(html), dest=buf, link_callback=_fetch_pdf_resource)
    return buf.getvalue()

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
