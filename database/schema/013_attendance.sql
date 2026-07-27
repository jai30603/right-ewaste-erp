-- Employee Attendance Schema v4.0
-- Module 4 Part 2: Attendance Management

CREATE TABLE IF NOT EXISTS employee_attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL,
    attendance_date DATE NOT NULL,
    check_in_time TEXT,
    check_out_time TEXT,
    attendance_status TEXT NOT NULL CHECK(attendance_status IN ('Present', 'Absent', 'Half Day', 'Leave', 'Holiday')),
    remarks TEXT,
    created_by TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(employee_id, attendance_date),
    FOREIGN KEY (employee_id) REFERENCES employees (id) ON DELETE CASCADE
);
