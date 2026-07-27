-- Employee Leave Management Schema v4.0
-- Module 4 Part 3: Leave Management

CREATE TABLE IF NOT EXISTS employee_leave_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    leave_name TEXT NOT NULL,
    leave_code TEXT UNIQUE NOT NULL,
    description TEXT,
    default_days REAL NOT NULL DEFAULT 0,
    is_paid INTEGER NOT NULL DEFAULT 1 CHECK(is_paid IN (0, 1)),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1)),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS employee_leave_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL,
    leave_type_id INTEGER NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    total_days REAL NOT NULL,
    reason TEXT NOT NULL,
    attachment_path TEXT,
    status TEXT NOT NULL DEFAULT 'Pending' CHECK(status IN ('Pending', 'Approved', 'Rejected', 'Cancelled')),
    approved_by TEXT,
    approval_date DATETIME,
    rejection_reason TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (employee_id) REFERENCES employees (id) ON DELETE CASCADE,
    FOREIGN KEY (leave_type_id) REFERENCES employee_leave_types (id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS employee_leave_balance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL,
    leave_type_id INTEGER NOT NULL,
    allocated_days REAL NOT NULL DEFAULT 0,
    used_days REAL NOT NULL DEFAULT 0,
    remaining_days REAL NOT NULL DEFAULT 0,
    financial_year INTEGER NOT NULL DEFAULT 2026,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(employee_id, leave_type_id, financial_year),
    FOREIGN KEY (employee_id) REFERENCES employees (id) ON DELETE CASCADE,
    FOREIGN KEY (leave_type_id) REFERENCES employee_leave_types (id) ON DELETE CASCADE
);

-- Seed default leave types if table is empty
INSERT OR IGNORE INTO employee_leave_types (leave_name, leave_code, description, default_days, is_paid, is_active)
VALUES 
    ('Casual Leave', 'CL', 'Casual leave for personal or urgent matters', 12.0, 1, 1),
    ('Sick Leave', 'SL', 'Leave for medical reasons and health recovery', 10.0, 1, 1),
    ('Earned Leave', 'EL', 'Accumulated privilege / annual leave', 15.0, 1, 1),
    ('Unpaid Leave', 'LWP', 'Leave without pay', 0.0, 0, 1);
