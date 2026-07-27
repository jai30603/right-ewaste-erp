-- 023_edms_content_intelligence.sql: Content Intelligence, Versioning & Tagging Schema for EDMS

CREATE TABLE IF NOT EXISTS document_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tag_name TEXT NOT NULL UNIQUE,
    color_hex TEXT DEFAULT '#3b82f6',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS document_tag_mappings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES document_tags(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(document_id, tag_id)
);

CREATE TABLE IF NOT EXISTS document_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    storage_path TEXT NOT NULL,
    size_bytes INTEGER NOT NULL DEFAULT 0,
    checksum_sha256 TEXT NOT NULL,
    changelog_notes TEXT,
    created_by INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(document_id, version_number)
);

CREATE TABLE IF NOT EXISTS document_relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    target_document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    relationship_type TEXT NOT NULL DEFAULT 'Related', -- Related, Parent-Child, Invoice-Quotation, Contract-SOP
    description TEXT,
    created_by INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_document_id, target_document_id, relationship_type)
);

CREATE INDEX IF NOT EXISTS idx_doc_versions_doc ON document_versions(document_id);
CREATE INDEX IF NOT EXISTS idx_doc_tag_map_doc ON document_tag_mappings(document_id);
CREATE INDEX IF NOT EXISTS idx_doc_rel_src ON document_relationships(source_document_id);
