-- Employee Payroll Management Schema v4.0
-- Module 4 Part 4: Payroll Basics

CREATE TABLE IF NOT EXISTS employee_salary_structure (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL,
    effective_from DATE NOT NULL,
    basic_salary REAL NOT NULL DEFAULT 0,
    hra REAL NOT NULL DEFAULT 0,
    conveyance_allowance REAL NOT NULL DEFAULT 0,
    medical_allowance REAL NOT NULL DEFAULT 0,
    special_allowance REAL NOT NULL DEFAULT 0,
    other_allowances REAL NOT NULL DEFAULT 0,
    provident_fund REAL NOT NULL DEFAULT 0,
    professional_tax REAL NOT NULL DEFAULT 0,
    income_tax REAL NOT NULL DEFAULT 0,
    other_deductions REAL NOT NULL DEFAULT 0,
    gross_salary REAL NOT NULL DEFAULT 0,
    net_salary REAL NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'Active' CHECK(status IN ('Active', 'Superceded', 'Inactive')),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (employee_id) REFERENCES employees (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS employee_payroll (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL,
    payroll_month INTEGER NOT NULL CHECK(payroll_month BETWEEN 1 AND 12),
    payroll_year INTEGER NOT NULL,
    working_days INTEGER NOT NULL DEFAULT 0,
    present_days REAL NOT NULL DEFAULT 0,
    leave_days REAL NOT NULL DEFAULT 0,
    absent_days REAL NOT NULL DEFAULT 0,
    gross_salary REAL NOT NULL DEFAULT 0,
    total_allowances REAL NOT NULL DEFAULT 0,
    total_deductions REAL NOT NULL DEFAULT 0,
    net_salary REAL NOT NULL DEFAULT 0,
    payroll_status TEXT NOT NULL DEFAULT 'Draft' CHECK(payroll_status IN ('Draft', 'Generated', 'Paid')),
    generated_by TEXT,
    generated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(employee_id, payroll_month, payroll_year),
    FOREIGN KEY (employee_id) REFERENCES employees (id) ON DELETE CASCADE
);
