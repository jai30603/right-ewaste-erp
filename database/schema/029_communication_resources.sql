-- Communication Module Phase 3 Schema Extension v1.0
-- Module 9.3: ERP Resource References (EDMS, Tasks, Locations, System Messages)

CREATE TABLE IF NOT EXISTS resource_references (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER NOT NULL,
    resource_type TEXT NOT NULL, -- 'DOCUMENT', 'TASK', 'LOCATION'
    resource_id TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (message_id) REFERENCES messages (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS document_references (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER NOT NULL,
    document_id INTEGER NOT NULL,
    FOREIGN KEY (message_id) REFERENCES messages (id) ON DELETE CASCADE,
    FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS task_references (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER NOT NULL,
    task_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    assignee TEXT,
    FOREIGN KEY (message_id) REFERENCES messages (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS location_references (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    address TEXT,
    FOREIGN KEY (message_id) REFERENCES messages (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS system_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    event_type TEXT NOT NULL, -- 'PURCHASE', 'SALES', 'INVENTORY', 'PROCESSING', 'HR'
    content TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES conversations (id) ON DELETE CASCADE
);

-- Mock tasks table to facilitate complete unit testing and resource selection
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    assignee_name TEXT,
    status TEXT DEFAULT 'PENDING',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_res_ref_msg ON resource_references(message_id);
CREATE INDEX IF NOT EXISTS idx_sys_msg_conv ON system_messages(conversation_id);
