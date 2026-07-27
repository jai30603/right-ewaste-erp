-- Platform Services Schema Extension v3.0
-- Module 3: Enterprise Core Platform Services

CREATE TABLE IF NOT EXISTS platform_event_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    source_module TEXT NOT NULL,
    payload TEXT,
    processed INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS scheduled_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_name TEXT UNIQUE NOT NULL,
    job_type TEXT NOT NULL,
    cron_expression TEXT,
    last_run DATETIME,
    next_run DATETIME,
    status TEXT DEFAULT 'ACTIVE',
    last_result TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS export_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_name TEXT NOT NULL,
    export_type TEXT NOT NULL,
    module TEXT NOT NULL,
    filters TEXT,
    status TEXT DEFAULT 'PENDING',
    file_path TEXT,
    requested_by TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME
);

CREATE TABLE IF NOT EXISTS dashboard_widgets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    widget_key TEXT UNIQUE NOT NULL,
    widget_name TEXT NOT NULL,
    widget_type TEXT NOT NULL,
    source_module TEXT NOT NULL,
    data_endpoint TEXT NOT NULL,
    icon TEXT DEFAULT 'bi bi-bar-chart',
    color TEXT DEFAULT '#3cb371',
    sort_order INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    requires_permission TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS kpi_definitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kpi_key TEXT UNIQUE NOT NULL,
    kpi_name TEXT NOT NULL,
    kpi_category TEXT NOT NULL,
    unit TEXT,
    formula_type TEXT DEFAULT 'SQL',
    formula TEXT NOT NULL,
    target_value REAL,
    warning_threshold REAL,
    critical_threshold REAL,
    is_active INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS kpi_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kpi_key TEXT NOT NULL,
    snapshot_date DATE NOT NULL,
    value REAL,
    computed_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_name TEXT NOT NULL,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    notification_type TEXT DEFAULT 'INFO',
    related_module TEXT,
    related_id TEXT,
    is_read INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
