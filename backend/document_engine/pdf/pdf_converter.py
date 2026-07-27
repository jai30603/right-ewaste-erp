import io
import os
from urllib.parse import urlparse
from xhtml2pdf import pisa
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Register SegoeUI font in ReportLab for the new package context
_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
_font_path = os.path.normpath(os.path.join(_root, 'static', 'fonts', 'SegoeUI.ttf'))
if os.path.exists(_font_path):
    try:
        pdfmetrics.registerFont(TTFont('Segoe UI', _font_path))
    except Exception:
        pass  # Font might already be registered by standard service

def _resolve_resource(uri, rel):
    """
    Resolves static paths for xhtml2pdf within the Document Engine context.
    """
    parsed = urlparse(uri)
    if parsed.scheme == 'file':
        path = parsed.path
        if path.startswith('/') and path[2:3] == ':':
            path = path[1:]
        return os.path.normpath(path)
        
    if uri.startswith('/static/'):
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        return os.path.normpath(os.path.join(root, uri.lstrip('/').replace('/', os.sep)))
        
    return uri

def convert_html_to_pdf(html_content):
    """
    Converts pure HTML text string into binary PDF bytes.
    """
    buf = io.BytesIO()
    pisa.CreatePDF(io.StringIO(html_content), dest=buf, link_callback=_resolve_resource)
    return buf.getvalue()
