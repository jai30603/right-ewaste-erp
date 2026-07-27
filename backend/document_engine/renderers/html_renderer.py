import json
from document_engine.placeholders.placeholder_resolver import resolve_placeholders
from document_engine.tables.table_renderer import render_dynamic_table
from document_engine.plugins.qr_plugin import QrPlugin
from document_engine.plugins.barcode_plugin import BarcodePlugin
from document_engine.plugins.watermark_plugin import WatermarkPlugin
from document_engine.plugins.signature_plugin import SignaturePlugin
from document_engine.plugins.chart_plugin import ChartPlugin

# Instantiate plugins
PLUGINS = {
    "qr": QrPlugin(),
    "barcode": BarcodePlugin(),
    "watermark": WatermarkPlugin(),
    "signature": SignaturePlugin(),
    "chart": ChartPlugin()
}

def render_css_styles(element_styles):
    """
    Translates dictionary-based designer styles into inline CSS strings.
    Supports properties: font-family, font-size, text-align, color, padding, margin, width, height, border, background-color.
    """
    if not element_styles:
        return ""
        
    styles = []
    properties_map = {
        "font": "font-family",
        "font_family": "font-family",
        "size": "font-size",
        "font_size": "font-size",
        "alignment": "text-align",
        "text_align": "text-align",
        "color": "color",
        "padding": "padding",
        "margin": "margin",
        "width": "width",
        "height": "height",
        "borders": "border",
        "border": "border",
        "background": "background-color",
        "background_color": "background-color"
    }
    
    for k, v in element_styles.items():
        css_prop = properties_map.get(k)
        if css_prop and v:
            # Ensure proper units (e.g. px, pt, %) for numerical properties
            val = str(v)
            if k in ["size", "font_size", "width", "height", "padding", "margin"] and val.isdigit():
                val = f"{val}px"
            styles.append(f"{css_prop}: {val};")
            
    return " ".join(styles)

def render_layout_to_html(layout_json, context):
    """
    Primary Renderer.
    Combines layout designer JSON structure and context variables to generate final HTML markup.
    """
    try:
        layout = json.loads(layout_json) if isinstance(layout_json, str) else layout_json
    except Exception:
        layout = {}
        
    if not layout or not isinstance(layout, dict):
        # Fallback standard template structure
        layout = {
            "layout": "A4_PORTRAIT",
            "margins": {"top": 36, "bottom": 36, "left": 36, "right": 36},
            "elements": [
                {"type": "logo"},
                {"type": "title", "content": "{{DECLARATION}}"},
                {"type": "dynamic_table"},
                {"type": "signature"}
            ]
        }
        
    page_layout = layout.get("layout", "A4_PORTRAIT")
    margins = layout.get("margins", {"top": 36, "bottom": 36, "left": 36, "right": 36})
    
    # Render main HTML wrapper with printable page layout setup
    html = []
    html.append("<!DOCTYPE html><html><head><meta charset='UTF-8'>")
    html.append(f"<title>{context.get('document_number', 'Document')}</title>")
    
    # Margins and layouts in CSS block compatible with xhtml2pdf Page Definitions
    orientation = "portrait" if "portrait" in page_layout.lower() else "landscape"
    html.append(f"""
    <style>
      @page {{
        size: a4 {orientation};
        margin: {margins.get('top', 36)}pt {margins.get('right', 36)}pt {margins.get('bottom', 36)}pt {margins.get('left', 36)}pt;
      }}
      body {{
        font-family: 'Segoe UI', sans-serif;
        font-size: 11px;
        color: #1f2937;
        background-color: #ffffff;
      }}
    </style>
    </head>
    <body>
    """)
    
    # Process layout elements
    for el in layout.get("elements", []):
        el_type = el.get("type", "text").lower()
        el_styles = el.get("styles", {})
        css_inline = render_css_styles(el_styles)
        
        # Check visibilities
        if el.get("visible") is False:
            continue
            
        # Renders elements based on designer type
        if el_type in ["text", "title", "dynamic_fields", "header", "footer"]:
            content = el.get("content", "")
            resolved_text = resolve_placeholders(content, context)
            tag = "div"
            if el_type == "title":
                tag = "h1"
            elif el_type == "header":
                tag = "header"
            elif el_type == "footer":
                tag = "footer"
            html.append(f'<{tag} style="{css_inline}">{resolved_text}</{tag}>')
            
        elif el_type in ["image", "logo", "stamp"]:
            path = el.get("path") or el.get("logo_path") or el.get("stamp_path")
            if not path:
                # Context fallback
                if el_type == "logo":
                    path = context.get("logo_path") or "/static/shared/logo.png"
                elif el_type == "stamp":
                    path = context.get("stamp_path")
                    
            if path:
                html.append(f'<div style="margin: 10px 0;"><img src="{path}" style="{css_inline}" /></div>')
                
        elif el_type == "dynamic_table":
            src_type = el.get("source_type", "purchase")
            tbl_data = context.get("materials", [])
            custom_grid = context.get("custom_table")
            table_html = render_dynamic_table(tbl_data, src_type, custom_grid)
            html.append(table_html)
            
        elif el_type == "page_break":
            html.append('<div style="page-break-after: always;"></div>')
            
        elif el_type == "line":
            color = el_styles.get("color", "#e2e8f0")
            height = el_styles.get("height", "1px")
            html.append(f'<hr style="border: none; border-top: {height} solid {color}; margin: 15px 0;" />')
            
        elif el_type in PLUGINS:
            # Render using dynamic plugin architecture
            plugin = PLUGINS[el_type]
            plugin_html = plugin.render(el, context)
            html.append(plugin_html)
            
        else:
            # Fallback block wrapper
            content = el.get("content", "")
            resolved_text = resolve_placeholders(content, context)
            html.append(f'<div style="{css_inline}">{resolved_text}</div>')
            
    html.append("</body></html>")
    return "\n".join(html)
