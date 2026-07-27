-- 032_edms_company_storage.sql: Schema extensions for multi-repository support and Company Storage

CREATE TABLE IF NOT EXISTS storage_repositories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_key TEXT NOT NULL UNIQUE, -- 'mydrive', 'company', 'chat_files', etc.
    repo_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Seed default repositories
INSERT OR IGNORE INTO storage_repositories (id, repo_key, repo_name) VALUES (1, 'mydrive', 'My Drive');
INSERT OR IGNORE INTO storage_repositories (id, repo_key, repo_name) VALUES (2, 'company', 'Company Storage');

CREATE TABLE IF NOT EXISTS repository_permissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repository_id INTEGER NOT NULL REFERENCES storage_repositories(id) ON DELETE CASCADE,
    role TEXT NOT NULL, -- 'User', 'Admin', 'Super Admin'
    can_create BOOLEAN NOT NULL DEFAULT 0,
    can_upload BOOLEAN NOT NULL DEFAULT 0,
    can_download BOOLEAN NOT NULL DEFAULT 0,
    can_rename BOOLEAN NOT NULL DEFAULT 0,
    can_delete BOOLEAN NOT NULL DEFAULT 0,
    can_move BOOLEAN NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(repository_id, role)
);

-- Seed permissions for My Drive (1)
INSERT OR IGNORE INTO repository_permissions (repository_id, role, can_create, can_upload, can_download, can_rename, can_delete, can_move)
VALUES (1, 'User', 1, 1, 1, 0, 0, 0);
INSERT OR IGNORE INTO repository_permissions (repository_id, role, can_create, can_upload, can_download, can_rename, can_delete, can_move)
VALUES (1, 'Admin', 1, 1, 1, 1, 1, 1);
INSERT OR IGNORE INTO repository_permissions (repository_id, role, can_create, can_upload, can_download, can_rename, can_delete, can_move)
VALUES (1, 'Super Admin', 1, 1, 1, 1, 1, 1);

-- Seed permissions for Company Storage (2)
INSERT OR IGNORE INTO repository_permissions (repository_id, role, can_create, can_upload, can_download, can_rename, can_delete, can_move)
VALUES (2, 'User', 1, 1, 1, 0, 0, 0);
INSERT OR IGNORE INTO repository_permissions (repository_id, role, can_create, can_upload, can_download, can_rename, can_delete, can_move)
VALUES (2, 'Admin', 1, 1, 1, 1, 1, 1);
INSERT OR IGNORE INTO repository_permissions (repository_id, role, can_create, can_upload, can_download, can_rename, can_delete, can_move)
VALUES (2, 'Super Admin', 1, 1, 1, 1, 1, 1);

CREATE TABLE IF NOT EXISTS company_storage_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repository_id INTEGER NOT NULL UNIQUE REFERENCES storage_repositories(id) ON DELETE CASCADE,
    folders_count INTEGER NOT NULL DEFAULT 0,
    files_count INTEGER NOT NULL DEFAULT 0,
    bytes_used INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Seed Company Storage usage tracking row
INSERT OR IGNORE INTO company_storage_usage (repository_id, folders_count, files_count, bytes_used) VALUES (2, 0, 0, 0);
