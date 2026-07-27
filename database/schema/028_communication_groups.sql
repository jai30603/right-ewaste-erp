-- Communication Module Phase 2 Schema Extension v1.0
-- Module 9.2: Groups, Collaboration & Pinned Messages

CREATE TABLE IF NOT EXISTS pinned_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    pinned_by_user_id INTEGER NOT NULL,
    pinned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
    FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE,
    FOREIGN KEY (pinned_by_user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(conversation_id, message_id)
);

CREATE TABLE IF NOT EXISTS mentions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL, -- mentioned user ID
    mentioned_by_user_id INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (mentioned_by_user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_pinned_messages_conversation_id ON pinned_messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_mentions_user_id ON mentions(user_id);
