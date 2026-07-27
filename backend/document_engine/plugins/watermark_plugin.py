from document_engine.plugins.base_plugin import BasePlugin

class WatermarkPlugin(BasePlugin):
    def initialize(self):
        pass
        
    def validate(self, config_data):
        return True, []
        
    def render(self, config_data, context):
        text = config_data.get("text", "CONFIDENTIAL")
        
        # Support dynamic text from context status
        if text == "STATUS":
            text = context.get("status", "DRAFT")
            
        color = config_data.get("color", "rgba(200, 200, 200, 0.25)")
        font_size = config_data.get("size", "60px")
        angle = config_data.get("angle", "-45")
        
        # Generates a CSS-rotated absolute positioned watermark block
        html = f"""
        <div style="
            position: absolute;
            top: 40%;
            left: 10%;
            width: 80%;
            text-align: center;
            font-size: {font_size};
            font-weight: bold;
            color: {color};
            transform: rotate({angle}deg);
            z-index: -100;
            pointer-events: none;
            text-transform: uppercase;
            letter-spacing: 10px;
        ">
            {text}
        </div>
        """
        return html
        
    def serialize(self):
        return {
            "name": "watermark_plugin",
            "description": "Renders background text watermark.",
            "properties": {
                "text": {"type": "string", "default": "DRAFT"},
                "color": {"type": "string", "default": "rgba(220, 220, 220, 0.2)"},
                "size": {"type": "string", "default": "65px"},
                "angle": {"type": "string", "default": "-45"}
            }
        }
