CREATE TABLE IF NOT EXISTS purchase_invoice (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    purchase_invoice_number TEXT NOT NULL UNIQUE,
    invoice_date DATE NOT NULL,
    supplier_id INTEGER NOT NULL,
    supplier_invoice_number TEXT,
    payment_mode TEXT,
    vehicle_number TEXT,
    transporter TEXT,
    remarks TEXT,
    subtotal REAL NOT NULL,
    cgst REAL DEFAULT 0,
    sgst REAL DEFAULT 0,
    igst REAL DEFAULT 0,
    gst_amount REAL DEFAULT 0,
    round_off REAL DEFAULT 0,
    grand_total REAL NOT NULL,
    status TEXT DEFAULT 'CONFIRMED',
    is_active INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (supplier_id) REFERENCES party(id)
);

CREATE TABLE IF NOT EXISTS purchase_invoice_item (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    purchase_invoice_id INTEGER NOT NULL,
    material_id INTEGER NOT NULL,
    quantity REAL NOT NULL,
    weight REAL DEFAULT 0,
    pieces INTEGER DEFAULT 0,
    rate REAL NOT NULL,
    amount REAL NOT NULL,
    FOREIGN KEY (purchase_invoice_id) REFERENCES purchase_invoice(id),
    FOREIGN KEY (material_id) REFERENCES material(id)
);
