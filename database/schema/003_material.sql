CREATE TABLE IF NOT EXISTS material (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    material_code TEXT NOT NULL UNIQUE,

    material_name TEXT NOT NULL,

    category TEXT,

    hsn_code TEXT NOT NULL,

    uom TEXT NOT NULL,

    gst_percentage REAL NOT NULL,

    description TEXT,

    is_active INTEGER NOT NULL DEFAULT 1,

    tracking_type TEXT NOT NULL DEFAULT 'BOTH' CHECK(tracking_type IN ('WEIGHT_ONLY', 'QUANTITY_ONLY', 'BOTH')),

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP

);