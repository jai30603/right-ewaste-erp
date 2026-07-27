-- 025_edms_multicloud_migration.sql: Multi-Cloud Storage & Migration Platform Schema

CREATE TABLE IF NOT EXISTS storage_routing_policies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scope TEXT NOT NULL UNIQUE, -- COMPANY, USER, BUSINESS_DOCUMENTS, SYSTEM, TEMPORARY
    target_provider_id INTEGER NOT NULL REFERENCES storage_providers(id),
    priority INTEGER DEFAULT 1,
    rules_json TEXT,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS storage_migration_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_name TEXT NOT NULL,
    source_provider_id INTEGER NOT NULL REFERENCES storage_providers(id),
    destination_provider_id INTEGER NOT NULL REFERENCES storage_providers(id),
    scope_json TEXT,
    total_files INTEGER DEFAULT 0,
    processed_files INTEGER DEFAULT 0,
    failed_files INTEGER DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'PENDING', -- PENDING, IN_PROGRESS, COMPLETED, FAILED, PAUSED, CANCELLED
    progress_percent INTEGER DEFAULT 0,
    error_log TEXT,
    created_by INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Seed AWS S3 Storage Provider Record
INSERT OR IGNORE INTO storage_providers (id, provider_key, provider_name, status, config_json, is_default)
VALUES (2, 's3', 'AWS S3 Bucket', 'INACTIVE', '{"bucket": "right-ewaste-docs", "region": "ap-south-1", "access_key": "MOCK_KEY", "secret_key": "MOCK_SECRET"}', 0);

-- Seed Default Routing Policies (Point all scopes to Local Storage #1 initially)
INSERT OR IGNORE INTO storage_routing_policies (scope, target_provider_id, priority)
VALUES 
    ('COMPANY', 1, 1),
    ('USER', 1, 1),
    ('BUSINESS_DOCUMENTS', 1, 1),
    ('SYSTEM', 1, 1),
    ('TEMPORARY', 1, 1);
