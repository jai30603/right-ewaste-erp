-- Communication Module Phase 4 Schema Extension v1.0
-- Module 9.4: ERP Integration, Resource Registration & Dashboards

CREATE TABLE IF NOT EXISTS module_registry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    module_name TEXT NOT NULL UNIQUE, -- 'EDMS', 'Tasks', 'Purchase', 'Sales', 'Inventory'
    module_icon TEXT NOT NULL,         -- Icon CSS classes
    config_json TEXT,                 -- Metadata configurations
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS resource_registry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    resource_type TEXT NOT NULL UNIQUE, -- 'DOCUMENT', 'TASK', 'LOCATION', 'PURCHASE_ORDER'
    source_module TEXT NOT NULL,
    config_json TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_module) REFERENCES module_registry (module_name) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS shared_resources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id TEXT,
    display_title TEXT NOT NULL,
    subtitle TEXT,
    preview_metadata TEXT,             -- JSON string containing custom properties
    deep_link TEXT NOT NULL,
    shared_by INTEGER NOT NULL,
    shared_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (message_id) REFERENCES messages (id) ON DELETE CASCADE,
    FOREIGN KEY (shared_by) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS dashboard_counters (
    user_id INTEGER PRIMARY KEY,
    unread_messages INTEGER DEFAULT 0,
    unread_direct INTEGER DEFAULT 0,
    unread_groups INTEGER DEFAULT 0,
    unread_mentions INTEGER DEFAULT 0,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS notification_preferences (
    user_id INTEGER PRIMARY KEY,
    preferences_json TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_shared_res_msg ON shared_resources(message_id);
CREATE INDEX IF NOT EXISTS idx_shared_res_type ON shared_resources(resource_type);
