from document_engine.plugins.base_plugin import BasePlugin

class SignaturePlugin(BasePlugin):
    def initialize(self):
        pass
        
    def validate(self, config_data):
        return True, []
        
    def render(self, config_data, context):
        title = config_data.get("title", "Authorized Signatory")
        name = config_data.get("name", context.get("company_name", ""))
        show_line = config_data.get("show_line", True)
        
        # Build signature block HTML
        html = []
        html.append('<div style="text-align: right; margin-top: 30px; font-size: 11px; float: right; width: 220px;">')
        if show_line:
            html.append('<div style="border-top: 1.5px solid #475569; width: 100%; margin-bottom: 5px;"></div>')
        html.append(f'<strong style="color: #1e293b; display: block;">{title}</strong>')
        if name:
            html.append(f'<span style="color: #64748b; font-size: 9.5px; display: block;">for {name}</span>')
        html.append('</div>')
        html.append('<div style="clear: both;"></div>')
        
        return "\n".join(html)
        
    def serialize(self):
        return {
            "name": "signature_plugin",
            "description": "Renders signature line block.",
            "properties": {
                "title": {"type": "string", "default": "Authorized Signatory"},
                "name": {"type": "string", "default": ""},
                "show_line": {"type": "boolean", "default": True}
            }
        }
