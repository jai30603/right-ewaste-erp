CREATE TABLE company (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    company_name TEXT NOT NULL,

    address_line_1 TEXT NOT NULL,

    address_line_2 TEXT,

    city TEXT NOT NULL,

    state TEXT NOT NULL,

    state_code TEXT NOT NULL,

    pincode TEXT NOT NULL,

    gstin TEXT NOT NULL UNIQUE,

    pan TEXT NOT NULL UNIQUE,

    cin TEXT UNIQUE,

    phone TEXT NOT NULL,

    email TEXT,

    website TEXT,

    logo_path TEXT,

    is_active INTEGER NOT NULL DEFAULT 1,

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    created_by INTEGER,

    updated_by INTEGER

);