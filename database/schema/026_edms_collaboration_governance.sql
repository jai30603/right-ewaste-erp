-- 026_edms_collaboration_governance.sql: Collaboration, Approvals, Comments & Locks Schema for EDMS

CREATE TABLE IF NOT EXISTS document_shares (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    shared_with_user_id INTEGER NOT NULL DEFAULT 1,
    permission_level TEXT NOT NULL DEFAULT 'View', -- View, Download, Comment, Edit, Approve, Full
    expiry_date TIMESTAMP,
    is_revoked BOOLEAN NOT NULL DEFAULT 0,
    created_by INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS document_comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    parent_comment_id INTEGER REFERENCES document_comments(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL DEFAULT 1,
    comment_text TEXT NOT NULL,
    is_resolved BOOLEAN NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS document_approval_workflows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    workflow_type TEXT NOT NULL DEFAULT 'STANDARD', -- STANDARD, PARALLEL, SEQUENTIAL
    current_step INTEGER DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'UNDER_REVIEW', -- DRAFT, SUBMITTED, UNDER_REVIEW, APPROVED, REJECTED, PUBLISHED
    requester_id INTEGER NOT NULL DEFAULT 1,
    reviewer_id INTEGER NOT NULL DEFAULT 1,
    reviewer_remarks TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS document_locks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL UNIQUE REFERENCES documents(id) ON DELETE CASCADE,
    locked_by_user_id INTEGER NOT NULL DEFAULT 1,
    lock_reason TEXT DEFAULT 'Editing',
    checked_out_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_locked BOOLEAN NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS edms_notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL DEFAULT 1,
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL, -- SHARED, REVIEW_REQUESTED, APPROVAL_PENDING, APPROVED, COMMENT_ADDED, CHECKOUT, CHECKIN
    message TEXT NOT NULL,
    is_read BOOLEAN NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS edms_governance_policies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    policy_name TEXT NOT NULL,
    policy_key TEXT NOT NULL UNIQUE,
    is_enabled BOOLEAN NOT NULL DEFAULT 0,
    config_json TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Seed Default Governance Policies
INSERT OR IGNORE INTO edms_governance_policies (policy_name, policy_key, is_enabled, config_json)
VALUES 
    ('Mandatory Approval Workflow', 'mandatory_approval', 0, '{"requires_approval_before_publish": true}'),
    ('Dynamic Watermarking', 'watermark_enabled', 1, '{"watermark_text": "CONFIDENTIAL - RIGHT EWASTE ERP"}'),
    ('Download Restriction Policy', 'download_restriction', 0, '{"restrict_external_downloads": true}'),
    ('Legal Hold Compliance', 'legal_hold_enabled', 0, '{"prevent_permanent_deletion": true}');
