-- Multi-Output Classification Engine & Disposal Queue Schema v4.0

-- 1. Add output_category column to processing_output
-- Output Categories: RECOVERABLE, REFURBISHABLE, DISPOSAL
CREATE TABLE IF NOT EXISTS processing_output_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    processing_job_id INTEGER NOT NULL,
    material_id INTEGER NOT NULL,
    quantity REAL NOT NULL DEFAULT 0,
    weight REAL NOT NULL DEFAULT 0,
    unit TEXT NOT NULL DEFAULT 'KGS',
    inventory_state TEXT NOT NULL DEFAULT 'RAW' CHECK(inventory_state IN ('RAW', 'PROCESSING', 'RECOVERED', 'FINISHED', 'RESERVED', 'REJECTED', 'DISPOSED')),
    output_category TEXT NOT NULL DEFAULT 'RECOVERABLE' CHECK(output_category IN ('RECOVERABLE', 'REFURBISHABLE', 'DISPOSAL')),
    recovered_from_material_id INTEGER REFERENCES material(id),
    FOREIGN KEY (processing_job_id) REFERENCES processing_job(id) ON DELETE CASCADE,
    FOREIGN KEY (material_id) REFERENCES material(id)
);

-- 2. Master Table for Disposal Materials
CREATE TABLE IF NOT EXISTS disposal_material_master (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    material_code TEXT NOT NULL UNIQUE,
    material_name TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL DEFAULT 'Hazardous E-Waste',
    is_hazardous INTEGER NOT NULL DEFAULT 1 CHECK(is_hazardous IN (0, 1)),
    default_unit TEXT NOT NULL DEFAULT 'KGS',
    is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1)),
    description TEXT,
    remarks TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 3. Master Table for Disposal Types
CREATE TABLE IF NOT EXISTS disposal_types_master (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type_name TEXT NOT NULL UNIQUE,
    description TEXT,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1)),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 4. Disposal Queue Table
CREATE TABLE IF NOT EXISTS disposal_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    processing_job_id INTEGER NOT NULL,
    processing_number TEXT NOT NULL,
    material_id INTEGER NOT NULL,
    material_name TEXT NOT NULL,
    quantity REAL NOT NULL DEFAULT 0,
    weight REAL NOT NULL DEFAULT 0,
    unit TEXT NOT NULL DEFAULT 'KGS',
    generated_date DATE NOT NULL,
    status TEXT NOT NULL DEFAULT 'Pending' CHECK(status IN ('Pending', 'Disposed', 'Cancelled')),
    disposal_type TEXT,
    disposal_vendor_id INTEGER REFERENCES party(id),
    vendor_name TEXT,
    transport_details TEXT,
    supporting_document_path TEXT,
    remarks TEXT,
    disposed_at DATETIME,
    disposed_by TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (processing_job_id) REFERENCES processing_job(id) ON DELETE CASCADE,
    FOREIGN KEY (material_id) REFERENCES material(id)
);

CREATE INDEX IF NOT EXISTS idx_disposal_queue_status ON disposal_queue(status);
CREATE INDEX IF NOT EXISTS idx_disposal_queue_job ON disposal_queue(processing_job_id);
CREATE INDEX IF NOT EXISTS idx_disposal_queue_date ON disposal_queue(generated_date);
