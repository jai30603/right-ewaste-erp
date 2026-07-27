from document_engine.plugins.base_plugin import BasePlugin

class ChartPlugin(BasePlugin):
    def initialize(self):
        pass
        
    def validate(self, config_data):
        return True, []
        
    def render(self, config_data, context):
        # Renders a simple progress/compliance chart block using HTML table bars.
        # This is fully offline-compatible and renders perfectly in PDFs.
        label = config_data.get("label", "Recycling Yield Compliance")
        percentage = float(config_data.get("percentage", context.get("yield_percentage", 95.0)))
        color = config_data.get("color", "#22c55e")
        bg_color = "#e2e8f0"
        
        html = f"""
        <div style="margin: 15px 0; font-family: sans-serif;">
            <div style="font-size: 10px; font-weight: bold; color: #475569; margin-bottom: 5px;">{label} ({percentage}%)</div>
            <table border="0" cellpadding="0" cellspacing="0" style="width: 100%; border-collapse: collapse; border-radius: 4px; overflow: hidden; height: 10px;">
                <tr>
                    <td style="width: {percentage}%; background-color: {color}; height: 10px; border: none; padding: 0;"></td>
                    <td style="width: {100 - percentage}%; background-color: {bg_color}; height: 10px; border: none; padding: 0;"></td>
                </tr>
            </table>
        </div>
        """
        return html
        
    def serialize(self):
        return {
            "name": "chart_plugin",
            "description": "Renders visual yield graphs.",
            "properties": {
                "label": {"type": "string", "default": "Yield compliance"},
                "percentage": {"type": "number", "default": 95.0},
                "color": {"type": "string", "default": "#22c55e"}
            }
        }
