-- 020_edms_foundation.sql: Foundational Schema for Enterprise Document Management System (EDMS)

CREATE TABLE IF NOT EXISTS storage_providers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_key TEXT NOT NULL UNIQUE,
    provider_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    config_json TEXT,
    is_default BOOLEAN NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS folders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    parent_folder_id INTEGER REFERENCES folders(id) ON DELETE CASCADE,
    folder_type TEXT NOT NULL DEFAULT 'COMPANY', -- COMPANY, USER, MODULE, SYSTEM, TEMPORARY, TRASH, ARCHIVE
    owner_user_id INTEGER,
    path TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    created_by INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_number TEXT NOT NULL UNIQUE,
    uuid TEXT NOT NULL UNIQUE,
    original_name TEXT NOT NULL,
    stored_name TEXT NOT NULL,
    extension TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    size_bytes INTEGER NOT NULL DEFAULT 0,
    checksum_sha256 TEXT NOT NULL,
    storage_provider_id INTEGER NOT NULL REFERENCES storage_providers(id),
    storage_path TEXT NOT NULL,
    owner_user_id INTEGER,
    folder_id INTEGER REFERENCES folders(id),
    status TEXT NOT NULL DEFAULT 'ACTIVE', -- ACTIVE, TRASH, ARCHIVED
    description TEXT,
    remarks TEXT,
    created_by INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS document_activity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    action TEXT NOT NULL, -- UPLOAD, DOWNLOAD, RENAME, MOVE, DELETE, RESTORE
    user_id INTEGER,
    resource_path TEXT,
    details_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_documents_uuid ON documents(uuid);
CREATE INDEX IF NOT EXISTS idx_documents_checksum ON documents(checksum_sha256);
CREATE INDEX IF NOT EXISTS idx_documents_folder ON documents(folder_id);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
CREATE INDEX IF NOT EXISTS idx_folders_uuid ON folders(uuid);
CREATE INDEX IF NOT EXISTS idx_folders_parent ON folders(parent_folder_id);
