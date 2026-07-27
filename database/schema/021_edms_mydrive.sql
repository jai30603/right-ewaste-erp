-- 021_edms_mydrive.sql: Favorites Schema for EDMS My Drive Module

CREATE TABLE IF NOT EXISTS document_favorites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    folder_id INTEGER REFERENCES folders(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CHECK (
        (document_id IS NOT NULL AND folder_id IS NULL) OR
        (document_id IS NULL AND folder_id IS NOT NULL)
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_doc_fav_user_doc ON document_favorites(user_id, document_id) WHERE document_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_doc_fav_user_folder ON document_favorites(user_id, folder_id) WHERE folder_id IS NOT NULL;
