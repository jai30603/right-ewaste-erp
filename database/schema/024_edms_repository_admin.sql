-- 024_edms_repository_admin.sql: EDMS Repository Administration & Configuration Schema

CREATE TABLE IF NOT EXISTS edms_system_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_key TEXT NOT NULL UNIQUE,
    config_value TEXT NOT NULL,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS edms_backup_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    backup_frequency TEXT NOT NULL DEFAULT 'DAILY', -- DAILY, WEEKLY, MONTHLY
    retention_days INTEGER NOT NULL DEFAULT 30,
    last_backup_at TIMESTAMP,
    last_backup_status TEXT DEFAULT 'SUCCESS',
    storage_location TEXT DEFAULT 'storage/backups',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS edms_maintenance_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'SUCCESS',
    details TEXT,
    executed_by INTEGER NOT NULL DEFAULT 1,
    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Seed Default Database-Driven Configuration Settings
INSERT OR IGNORE INTO edms_system_configs (config_key, config_value, description)
VALUES 
    ('max_upload_size_mb', '100', 'Maximum allowable file upload size in megabytes'),
    ('allowed_file_types', 'pdf,png,jpg,jpeg,gif,webp,svg,xls,xlsx,csv,doc,docx,txt,json,xml,md,zip,rar', 'Allowed document extensions comma separated'),
    ('duplicate_policy', 'WARN', 'Duplicate file handling policy: WARN, ALLOW, BLOCK'),
    ('default_classification', 'INTERNAL', 'Default classification for new document uploads'),
    ('default_lifecycle', 'UPLOADED', 'Default lifecycle status for new document uploads');

INSERT OR IGNORE INTO edms_backup_configs (id, backup_frequency, retention_days, storage_location)
VALUES (1, 'DAILY', 30, 'storage/backups');
