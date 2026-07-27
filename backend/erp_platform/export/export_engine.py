"""
Export Engine
Generate CSV and JSON exports for tabular data.
Used by all modules for downloading data.
"""
import csv
import io
import json
from datetime import datetime
from flask import Response


def export_to_csv(data: list, filename: str, columns: list = None) -> Response:
    """
    Export a list of dicts to CSV as a Flask download response.

    :param data: list of dicts
    :param filename: desired filename (without extension or timestamp)
    :param columns: ordered list of column keys to include
    """
    if not data:
        data = [{}]
    if not columns:
        columns = list(data[0].keys()) if data else []

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=columns, extrasaction='ignore')
    writer.writeheader()
    writer.writerows(data)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    full_filename = f"{filename}_{timestamp}.csv"

    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={"Content-Disposition": f"attachment; filename={full_filename}"}
    )


def export_to_json(data: list, filename: str) -> Response:
    """Export a list of dicts as a JSON download response."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    full_filename = f"{filename}_{timestamp}.json"
    return Response(
        json.dumps(data, indent=2, default=str),
        mimetype='application/json',
        headers={"Content-Disposition": f"attachment; filename={full_filename}"}
    )


def format_for_display(data: list, columns: list = None) -> dict:
    """Return structured data ready for template rendering."""
    if not data:
        return {"columns": columns or [], "rows": [], "count": 0}
    if not columns:
        columns = list(data[0].keys()) if data else []
    return {
        "columns": columns,
        "rows": data,
        "count": len(data),
        "exported_at": datetime.now().isoformat()
    }
