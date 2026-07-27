from document_engine.plugins.base_plugin import BasePlugin

class BarcodePlugin(BasePlugin):
    def initialize(self):
        pass
        
    def validate(self, config_data):
        errors = []
        if not config_data.get("value"):
            errors.append("Barcode value is required.")
        return len(errors) == 0, errors
        
    def render(self, config_data, context):
        value = config_data.get("value", "")
        # Resolve any context placeholders inside the value (e.g. {{PURCHASE_NO}})
        for k, v in context.items():
            if v is not None:
                value = value.replace(f"{{{{{k}}}}}", str(v))
                
        barcode_type = config_data.get("type", "code128").lower()
        height = int(config_data.get("height", 30))
        
        # xhtml2pdf has built-in support for <pdf:barcode> tag.
        # This compiles cleanly offline to ReportLab's flowable.
        return f'<pdf:barcode value="{value}" type="{barcode_type}" barheight="{height}" />'
        
    def serialize(self):
        return {
            "name": "barcode_plugin",
            "description": "Renders a standard 1D Barcode (e.g. Code 128).",
            "properties": {
                "value": {"type": "string", "default": "{{BARCODE}}"},
                "type": {"type": "string", "default": "code128"},
                "height": {"type": "integer", "default": 30}
            }
        }
