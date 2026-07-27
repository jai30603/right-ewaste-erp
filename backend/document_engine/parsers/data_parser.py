import csv
import io
import openpyxl

def parse_clipboard_table(tsv_data):
    """
    Parses tab-separated text copied from spreadsheets/Excel sheets into rows.
    """
    if not tsv_data:
        return []
        
    rows = []
    # Replace carriage returns and split by lines
    lines = tsv_data.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    
    for line in lines:
        if not line.strip():
            continue
        # Split line by tabs
        cols = line.split('\t')
        rows.append([c.strip() for c in cols])
        
    return rows

def parse_csv_file(file_bytes):
    """
    Parses raw CSV bytes into simple rows list.
    """
    try:
        text = file_bytes.decode('utf-8')
    except UnicodeDecodeError:
        text = file_bytes.decode('latin-1')
        
    reader = csv.reader(io.StringIO(text))
    rows = []
    for r in reader:
        if any(r):
            rows.append([x.strip() for x in r])
    return rows

def parse_excel_file(file_path_or_bytes):
    """
    Parses uploaded Excel binary spreadsheet (.xlsx) using openpyxl.
    """
    try:
        if isinstance(file_path_or_bytes, bytes):
            wb = openpyxl.load_workbook(io.BytesIO(file_path_or_bytes), data_only=True, read_only=True)
        else:
            wb = openpyxl.load_workbook(file_path_or_bytes, data_only=True, read_only=True)
            
        sheet = wb.active
        rows = []
        for r in sheet.iter_rows(values_only=True):
            if any(r is not None for x in r):
                rows.append([str(x).strip() if x is not None else "" for x in r])
        return rows
    except Exception as exc:
        print(f"Excel parsing failed: {exc}")
        return []
