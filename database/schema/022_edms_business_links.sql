-- 022_edms_business_links.sql: Generic Business Record Attachment Schema for EDMS

CREATE TABLE IF NOT EXISTS document_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    module_name TEXT NOT NULL, -- purchase, sales, inventory, processing, employee, party, certificate, report
    record_type TEXT NOT NULL DEFAULT 'record', -- invoice, item, batch, profile, job, certificate, report
    record_id INTEGER NOT NULL,
    category TEXT NOT NULL DEFAULT 'Other', -- Invoice, Quotation, Photo, Certificate, Government, Legal, Financial, Technical, Compliance, Warranty, Agreement, Report, Other
    relationship_type TEXT DEFAULT 'Attachment',
    description TEXT,
    uploaded_by INTEGER NOT NULL DEFAULT 1,
    uploaded_on TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_doc_links_module_record ON document_links(module_name, record_id);
CREATE INDEX IF NOT EXISTS idx_doc_links_document ON document_links(document_id);
CREATE INDEX IF NOT EXISTS idx_doc_links_category ON document_links(category);
