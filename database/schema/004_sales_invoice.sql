CREATE TABLE IF NOT EXISTS sales_invoice (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    invoice_number TEXT NOT NULL UNIQUE,

    invoice_date DATE NOT NULL,

    party_id INTEGER NOT NULL,

    payment_mode TEXT,

    transporter TEXT,

    vehicle_number TEXT,

    subtotal REAL NOT NULL,

    cgst REAL DEFAULT 0,

    sgst REAL DEFAULT 0,

    igst REAL DEFAULT 0,

    round_off REAL DEFAULT 0,

    grand_total REAL NOT NULL,

    remarks TEXT,

    status TEXT DEFAULT 'CONFIRMED',

    is_active INTEGER DEFAULT 1,

    eway_bill_number TEXT,

    reference_number TEXT,

    created_by TEXT,

    updated_by TEXT,

    print_count INTEGER DEFAULT 0,

    pdf_download_count INTEGER DEFAULT 0,

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (party_id) REFERENCES party(id)

);