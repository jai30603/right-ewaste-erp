CREATE TABLE sales_invoice_item (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    sales_invoice_id INTEGER NOT NULL,

    material_id INTEGER NOT NULL,

    quantity REAL NOT NULL,

    rate REAL NOT NULL,

    amount REAL NOT NULL,

    FOREIGN KEY (sales_invoice_id) REFERENCES sales_invoice(id),

    FOREIGN KEY (material_id) REFERENCES material(id)

);