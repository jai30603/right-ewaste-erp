CREATE TABLE IF NOT EXISTS party (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    party_code TEXT NOT NULL UNIQUE,

    company_name TEXT NOT NULL,

    contact_person TEXT,

    party_type TEXT NOT NULL CHECK(party_type IN ('CUSTOMER', 'SUPPLIER', 'BOTH')),

    gstin TEXT UNIQUE,

    pan TEXT,

    phone TEXT NOT NULL,

    alternate_phone TEXT,

    email TEXT,

    billing_address TEXT NOT NULL,

    shipping_address TEXT,

    city TEXT NOT NULL,

    state TEXT NOT NULL,

    state_code TEXT NOT NULL,

    pincode TEXT,

    remarks TEXT,

    is_active INTEGER NOT NULL DEFAULT 1,

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP

);