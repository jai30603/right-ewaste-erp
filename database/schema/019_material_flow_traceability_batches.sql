-- Material Flow Engine, Batches & End-to-End Traceability Schema v5.0

-- 1. Material Batch Table
CREATE TABLE IF NOT EXISTS material_batch (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_number TEXT NOT NULL UNIQUE,
    purchase_invoice_id INTEGER REFERENCES purchase_invoice(id) ON DELETE SET NULL,
    purchase_invoice_number TEXT,
    supplier_id INTEGER REFERENCES party(id) ON DELETE SET NULL,
    supplier_name TEXT,
    purchase_date DATE NOT NULL,
    material_id INTEGER NOT NULL REFERENCES material(id),
    material_name TEXT NOT NULL,
    quantity REAL NOT NULL DEFAULT 0,
    weight REAL NOT NULL DEFAULT 0,
    remaining_quantity REAL NOT NULL DEFAULT 0,
    remaining_weight REAL NOT NULL DEFAULT 0,
    warehouse_id INTEGER NOT NULL DEFAULT 1 REFERENCES warehouse(id),
    status TEXT NOT NULL DEFAULT 'IN_STORE' CHECK(status IN ('RECEIVED', 'IN_STORE', 'IN_PROCESSING', 'PROCESSED', 'DISPOSED', 'SOLD')),
    financial_valuation REAL DEFAULT 0.0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_batch_number ON material_batch(batch_number);
CREATE INDEX IF NOT EXISTS idx_batch_material ON material_batch(material_id);
CREATE INDEX IF NOT EXISTS idx_batch_purchase ON material_batch(purchase_invoice_id);
CREATE INDEX IF NOT EXISTS idx_batch_status ON material_batch(status);

-- 2. Add columns to stock_movement for Batch Traceability and Financial Valuation
-- Columns added via database.py migrations: batch_id, batch_number, from_location, to_location, financial_valuation, cogs, disposal_cost

-- 3. Add columns to processing_input, processing_output, disposal_queue for parent batch inheritance
-- Columns added via database.py migrations: batch_id, batch_number, parent_batch_id, parent_batch_number
