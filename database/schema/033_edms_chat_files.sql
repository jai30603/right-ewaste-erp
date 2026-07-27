-- 033_edms_chat_files.sql: Schema extensions for Phase 3 Chat Files
CREATE TABLE IF NOT EXISTS chat_file_reference (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    sender_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    shared_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS conversation_attachment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS attachment_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    original_repository_id INTEGER NOT NULL REFERENCES storage_repositories(id) ON DELETE CASCADE,
    file_type TEXT,
    file_size INTEGER,
    sender_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    shared_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Seed chat files repository entry
INSERT OR IGNORE INTO storage_repositories (id, repo_key, repo_name) VALUES (3, 'chatfiles', 'Chat Files');

-- Seed permissions for Chat Files (all roles have download access, but no modification/deletion/upload allowed from within this repo view)
INSERT OR IGNORE INTO repository_permissions (repository_id, role, can_create, can_upload, can_download, can_rename, can_move, can_delete) 
VALUES (3, 'User', 0, 0, 1, 0, 0, 0);
INSERT OR IGNORE INTO repository_permissions (repository_id, role, can_create, can_upload, can_download, can_rename, can_move, can_delete) 
VALUES (3, 'Admin', 0, 0, 1, 0, 0, 0);
INSERT OR IGNORE INTO repository_permissions (repository_id, role, can_create, can_upload, can_download, can_rename, can_move, can_delete) 
VALUES (3, 'Super Admin', 0, 0, 1, 0, 0, 0);
