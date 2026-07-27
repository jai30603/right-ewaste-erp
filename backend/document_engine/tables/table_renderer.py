def render_dynamic_table(data_source, source_type="purchase", custom_data=None):
    """
    Decoupled table renderer.
    Renders structured rows into a printable compliant HTML table.
    """
    html = []
    
    # Standard CSS styles for printable tables
    html.append("""
    <style>
      table.document-items-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 10.5px;
        margin: 15px 0;
      }
      table.document-items-table thead tr {
        background-color: #1e3a8a;
        color: #ffffff;
      }
      table.document-items-table th {
        padding: 8px 10px;
        font-weight: 600;
        text-align: left;
      }
      table.document-items-table td {
        padding: 8px 10px;
        border-bottom: 1.5px solid #e2e8f0;
      }
      table.document-items-table tbody tr:nth-child(even) {
        background-color: #f8fafc;
      }
    </style>
    """)
    
    html.append('<table class="document-items-table">')
    
    # 1. Determine columns and rows based on source
    headers = []
    rows = []
    totals = {}
    
    if source_type == "custom" and custom_data:
        # custom_data is expected to be a list of lists (grid) or list of dicts.
        # If it is a list of dicts:
        if isinstance(custom_data, list) and len(custom_data) > 0:
            if isinstance(custom_data[0], dict):
                headers = list(custom_data[0].keys())
                for item in custom_data:
                    rows.append([str(item.get(h, "")) for h in headers])
            elif isinstance(custom_data[0], list):
                headers = [str(x) for x in custom_data[0]]
                for item in custom_data[1:]:
                    rows.append([str(x) for x in item])
    elif source_type == "purchase" and data_source:
        # data_source is purchase items: [{material_name, quantity, weight, uom, rate, amount}]
        headers = ["Material Name / Description", "Quantity", "Weight"]
        total_qty = 0.0
        total_wt = 0.0
        for item in data_source:
            qty = float(item.get("quantity") or 0.0)
            wt = float(item.get("weight") or 0.0)
            uom = item.get("uom") or "KG"
            total_qty += qty
            total_wt += wt
            rows.append([
                item.get("material_name", "Unknown Material"),
                f"{qty} {uom}",
                f"{wt:.2f} KG"
            ])
        totals = {
            "label": "Total Certified Yield",
            "values": ["—", f"{total_wt:.2f} KG"]
        }
    elif source_type == "processing" and data_source:
        # data_source is processing outputs
        headers = ["Material Code", "Material Name / Description", "Quantity", "Weight"]
        total_wt = 0.0
        for item in data_source:
            wt = float(item.get("weight") or 0.0)
            total_wt += wt
            rows.append([
                item.get("material_code", ""),
                item.get("material_name", ""),
                f"{item.get('quantity', 0)} {item.get('unit', 'KG')}",
                f"{wt:.2f} KG"
            ])
        totals = {
            "label": "Total Processed Yield",
            "values": ["", "—", f"{total_wt:.2f} KG"]
        }
    else:
        # Generic fallback
        headers = ["Description", "Quantity", "Weight"]
        rows = [["No data items found", "0", "0.00 KG"]]
        
    # Build header HTML
    html.append('<thead><tr>')
    for h in headers:
        html.append(f'<th>{h}</th>')
    html.append('</tr></thead>')
    
    # Build body HTML
    html.append('<tbody>')
    for r in rows:
        html.append('<tr>')
        for val in r:
            html.append(f'<td>{val}</td>')
        html.append('</tr>')
        
    # Build totals row if available
    if totals:
        html.append('<tr style="background-color: #f1f5f9; font-weight: bold;">')
        html.append(f'<td>{totals["label"]}</td>')
        for val in totals["values"]:
            html.append(f'<td>{val}</td>')
        html.append('</tr>')
        
    html.append('</tbody>')
    html.append('</table>')
    
    return "\n".join(html)
