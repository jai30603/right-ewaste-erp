-- 034_edms_storage_providers.sql: Schema extensions for Phase 4 Storage Providers
CREATE TABLE IF NOT EXISTS storage_providers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_key TEXT UNIQUE NOT NULL, -- 'aws_s3', 'azure_blob', 'gcs'
    provider_name TEXT NOT NULL,
    provider_type TEXT NOT NULL,
    config_json TEXT NOT NULL,         -- JSON string of credentials encrypted
    is_active BOOLEAN NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'NOT_CONNECTED',
    health_status TEXT NOT NULL DEFAULT 'UNKNOWN',
    last_connection_test DATETIME,
    last_synchronization DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS storage_health (
    provider_id INTEGER PRIMARY KEY REFERENCES storage_providers(id) ON DELETE CASCADE,
    connection_status TEXT,
    bucket_availability BOOLEAN,
    last_successful_connection DATETIME,
    last_error TEXT,
    total_files INTEGER DEFAULT 0,
    total_folders INTEGER DEFAULT 0,
    storage_usage_bytes INTEGER DEFAULT 0,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS workspace_initialization (
    provider_id INTEGER PRIMARY KEY REFERENCES storage_providers(id) ON DELETE CASCADE,
    initialized_at DATETIME,
    status TEXT DEFAULT 'PENDING'
);

-- Seed default storage providers configuration template (empty JSON credentials)
INSERT OR IGNORE INTO storage_providers (id, provider_key, provider_name, provider_type, config_json, is_active, status)
VALUES (2, 'aws_s3', 'Amazon AWS S3', 'AWS_S3', 'KTQ=', 0, 'NOT_CONNECTED');

INSERT OR IGNORE INTO storage_providers (id, provider_key, provider_name, provider_type, config_json, is_active, status)
VALUES (3, 'azure_blob', 'Microsoft Azure Blob', 'AZURE_BLOB', 'KTQ=', 0, 'NOT_CONNECTED');

INSERT OR IGNORE INTO storage_providers (id, provider_key, provider_name, provider_type, config_json, is_active, status)
VALUES (4, 'gcs', 'Google Cloud Storage', 'GCS', 'KTQ=', 0, 'NOT_CONNECTED');
