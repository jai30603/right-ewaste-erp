-- 031_edms_mydrive_usage.sql: Schema for My Drive storage quota, usage, and recycle bin management

CREATE TABLE IF NOT EXISTS user_storage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    storage_limit_bytes INTEGER NOT NULL DEFAULT 5368709120, -- 5 GB default limit
    storage_used_bytes INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS recycle_bin (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    item_type TEXT NOT NULL, -- 'FILE' or 'FOLDER'
    item_id INTEGER NOT NULL,
    original_name TEXT NOT NULL,
    original_parent_id INTEGER,
    original_path TEXT NOT NULL,
    deleted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS storage_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    folders_count INTEGER NOT NULL DEFAULT 0,
    files_count INTEGER NOT NULL DEFAULT 0,
    bytes_used INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
