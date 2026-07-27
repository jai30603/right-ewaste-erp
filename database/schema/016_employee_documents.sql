-- Employee Documents Schema v4.0
-- Module 4 Part 5: Reports, Analytics & Document Management

CREATE TABLE IF NOT EXISTS employee_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL,
    document_category TEXT NOT NULL CHECK(document_category IN ('Aadhaar', 'PAN', 'Offer Letter', 'Appointment Letter', 'Salary Revision Letter', 'Experience Letter', 'ID Card', 'Other')),
    document_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_size INTEGER DEFAULT 0,
    file_type TEXT,
    uploaded_by TEXT,
    uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (employee_id) REFERENCES employees (id) ON DELETE CASCADE
);
