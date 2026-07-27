-- Employee Management Schema v4.0
-- Module 4: Employee Master & Profile Management

CREATE TABLE IF NOT EXISTS employees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_code TEXT UNIQUE NOT NULL,
    first_name TEXT NOT NULL,
    last_name TEXT,
    full_name TEXT NOT NULL,
    gender TEXT,
    date_of_birth DATE,
    mobile_number TEXT UNIQUE,
    email TEXT UNIQUE,
    profile_photo TEXT,
    joining_date DATE,
    department TEXT,
    designation TEXT,
    reporting_manager TEXT,
    employment_type TEXT,
    status TEXT NOT NULL DEFAULT 'Active',
    current_address TEXT,
    permanent_address TEXT,
    aadhaar_number TEXT UNIQUE,
    pan_number TEXT UNIQUE,
    user_id INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,
    updated_by TEXT,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS employee_bank_details (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL UNIQUE,
    bank_name TEXT,
    account_holder_name TEXT,
    account_number TEXT,
    ifsc_code TEXT,
    branch_name TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (employee_id) REFERENCES employees (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS employee_emergency_contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL,
    contact_name TEXT,
    relationship TEXT,
    mobile_number TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (employee_id) REFERENCES employees (id) ON DELETE CASCADE
);
