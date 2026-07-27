-- Factory Report Generation & Compliance History Schema v4.0

CREATE TABLE IF NOT EXISTS factory_report_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_date DATE NOT NULL,
    report_month INTEGER NOT NULL,
    report_year INTEGER NOT NULL,
    template_version TEXT NOT NULL DEFAULT 'v1.0',
    file_path TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_size INTEGER DEFAULT 0,
    generated_by TEXT NOT NULL,
    generated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL DEFAULT 'Generated',
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_factory_report_date ON factory_report_history(report_date);
