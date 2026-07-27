CREATE TABLE IF NOT EXISTS processing_job (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    processing_number TEXT NOT NULL UNIQUE,
    processing_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'DRAFT' CHECK(status IN ('DRAFT', 'READY', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED', 'ARCHIVED')),
    priority TEXT NOT NULL DEFAULT 'NORMAL' CHECK(priority IN ('LOW', 'NORMAL', 'HIGH', 'URGENT')),
    operator_id TEXT NOT NULL,
    remarks TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS processing_input (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    processing_job_id INTEGER NOT NULL,
    material_id INTEGER NOT NULL,
    quantity REAL NOT NULL DEFAULT 0,
    weight REAL NOT NULL DEFAULT 0,
    unit TEXT NOT NULL,
    processing_type TEXT NOT NULL CHECK(processing_type IN ('REFURBISHMENT', 'DISMANTLING', 'SORTING', 'INTERNAL_CONSUMPTION', 'WEIGHT_ADJUSTMENT')),
    inventory_reference TEXT,
    FOREIGN KEY (processing_job_id) REFERENCES processing_job(id) ON DELETE CASCADE,
    FOREIGN KEY (material_id) REFERENCES material(id)
);

CREATE TABLE IF NOT EXISTS processing_output (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    processing_job_id INTEGER NOT NULL,
    material_id INTEGER NOT NULL,
    quantity REAL NOT NULL DEFAULT 0,
    weight REAL NOT NULL DEFAULT 0,
    unit TEXT NOT NULL,
    inventory_state TEXT NOT NULL DEFAULT 'RAW' CHECK(inventory_state IN ('RAW', 'PROCESSING', 'RECOVERED', 'FINISHED', 'RESERVED', 'REJECTED', 'DISPOSED')),
    recovered_from_material_id INTEGER REFERENCES material(id),
    FOREIGN KEY (processing_job_id) REFERENCES processing_job(id) ON DELETE CASCADE,
    FOREIGN KEY (material_id) REFERENCES material(id),
    FOREIGN KEY (recovered_from_material_id) REFERENCES material(id)
);

CREATE TABLE IF NOT EXISTS processing_loss (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    processing_job_id INTEGER NOT NULL,
    loss_weight REAL NOT NULL DEFAULT 0,
    loss_reason TEXT NOT NULL CHECK(loss_reason IN ('WATER', 'DUST', 'PACKAGING', 'BROKEN_MATERIAL', 'NON_RECYCLABLE_WASTE', 'UNKNOWN', 'OTHER')),
    remarks TEXT,
    FOREIGN KEY (processing_job_id) REFERENCES processing_job(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS processing_job_activity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    processing_job_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    performed_by TEXT NOT NULL,
    remarks TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (processing_job_id) REFERENCES processing_job(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_processing_job_status ON processing_job(status);
CREATE INDEX IF NOT EXISTS idx_processing_job_number ON processing_job(processing_number);
CREATE INDEX IF NOT EXISTS idx_processing_input_job ON processing_input(processing_job_id);
CREATE INDEX IF NOT EXISTS idx_processing_output_job ON processing_output(processing_job_id);
