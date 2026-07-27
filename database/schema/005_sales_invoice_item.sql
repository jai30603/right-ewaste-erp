CREATE TABLE IF NOT EXISTS sales_invoice_item (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    sales_invoice_id INTEGER NOT NULL,

    material_id INTEGER NOT NULL,

    quantity REAL NOT NULL,

    weight REAL DEFAULT 0,

    rate REAL NOT NULL,

    amount REAL NOT NULL,

    FOREIGN KEY (sales_invoice_id) REFERENCES sales_invoice(id),

    FOREIGN KEY (material_id) REFERENCES material(id)

);