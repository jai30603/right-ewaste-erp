from document_engine.plugins.base_plugin import BasePlugin
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.barcode.qr import QrCodeWidget

class QrPlugin(BasePlugin):
    def initialize(self):
        pass
        
    def validate(self, config_data):
        errors = []
        if not config_data.get("value"):
            errors.append("QR Code value is required.")
        return len(errors) == 0, errors
        
    def render(self, config_data, context):
        value = config_data.get("value", "")
        # Resolve any context placeholders inside the value (e.g. {{CERTIFICATE_NO}})
        for k, v in context.items():
            if v is not None:
                value = value.replace(f"{{{{{k}}}}}", str(v))
                
        size = int(config_data.get("size", 100))
        
        # Build ReportLab QR code matrix
        d = Drawing(size, size)
        qr = QrCodeWidget(value)
        d.add(qr)
        qr.draw()  # Triggers matrix generation
        
        modules = qr.qr.modules
        dim = len(modules)
        
        # Build an HTML table representation of the QR code.
        # This is 100% offline, requires zero external libraries, and compiles perfectly in xhtml2pdf.
        cell_size = max(1.0, float(size) / dim)
        
        html = [f'<table border="0" cellpadding="0" cellspacing="0" style="border-collapse: collapse; width: {size}px; height: {size}px; line-height: 0; font-size: 0;">']
        for row in modules:
            html.append('<tr>')
            for col in row:
                color = "#000000" if col else "#ffffff"
                html.append(f'<td style="width: {cell_size}px; height: {cell_size}px; background-color: {color}; padding: 0; margin: 0; border: none;"></td>')
            html.append('</tr>')
        html.append('</table>')
        
        return "\n".join(html)
        
    def serialize(self):
        return {
            "name": "qr_plugin",
            "description": "Renders a dynamic verification QR code.",
            "properties": {
                "value": {"type": "string", "default": "{{QR_CODE}}"},
                "size": {"type": "integer", "default": 100}
            }
        }
