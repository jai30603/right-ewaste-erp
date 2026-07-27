CREATE TABLE IF NOT EXISTS warehouse (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    warehouse_name TEXT NOT NULL UNIQUE,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO warehouse (id, warehouse_name) VALUES (1, 'Main Warehouse');

CREATE TABLE IF NOT EXISTS inventory_balance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    material_id INTEGER NOT NULL,
    warehouse_id INTEGER NOT NULL DEFAULT 1,
    inventory_state TEXT NOT NULL DEFAULT 'RAW'
        CHECK(inventory_state IN ('RAW', 'PROCESSING', 'RECOVERED', 'FINISHED', 'RESERVED', 'REJECTED', 'DISPOSED')),
    current_quantity REAL NOT NULL DEFAULT 0,
    current_weight REAL NOT NULL DEFAULT 0,
    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(material_id, warehouse_id, inventory_state),
    FOREIGN KEY (material_id) REFERENCES material(id),
    FOREIGN KEY (warehouse_id) REFERENCES warehouse(id)
);

CREATE TABLE IF NOT EXISTS stock_movement (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    movement_key TEXT NOT NULL UNIQUE,
    material_id INTEGER NOT NULL,
    warehouse_id INTEGER NOT NULL DEFAULT 1,
    inventory_state TEXT NOT NULL,
    movement_type TEXT NOT NULL CHECK(movement_type IN (
        'PURCHASE', 'SALE', 'PROCESSING', 'REFURBISHMENT', 'DISMANTLING', 'SORTING',
        'INTERNAL_CONSUMPTION', 'WEIGHT_ADJUSTMENT', 'MANUAL_ADJUSTMENT', 'RETURN', 'TRANSFER'
    )),
    reference_type TEXT NOT NULL,
    reference_id INTEGER,
    reference_number TEXT,
    quantity_before REAL NOT NULL,
    quantity_change REAL NOT NULL,
    quantity_after REAL NOT NULL,
    weight_before REAL NOT NULL,
    weight_change REAL NOT NULL,
    weight_after REAL NOT NULL,
    performed_by TEXT NOT NULL DEFAULT 'System User',
    remarks TEXT,
    processing_job_reference TEXT,
    certificate_reference TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (material_id) REFERENCES material(id),
    FOREIGN KEY (warehouse_id) REFERENCES warehouse(id)
);

CREATE INDEX IF NOT EXISTS idx_stock_movement_material_date ON stock_movement(material_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_stock_movement_reference ON stock_movement(reference_type, reference_id);
CREATE INDEX IF NOT EXISTS idx_inventory_balance_state ON inventory_balance(inventory_state, material_id);

CREATE TABLE IF NOT EXISTS inventory_metadata (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
