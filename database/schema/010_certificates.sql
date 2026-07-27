CREATE TABLE IF NOT EXISTS certificate_template (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_key TEXT NOT NULL UNIQUE,
    template_name TEXT NOT NULL,
    title TEXT NOT NULL,
    declaration_text TEXT NOT NULL,
    show_logo INTEGER NOT NULL DEFAULT 1 CHECK(show_logo IN (0, 1)),
    show_customer_details INTEGER NOT NULL DEFAULT 1 CHECK(show_customer_details IN (0, 1)),
    show_purchase_references INTEGER NOT NULL DEFAULT 1 CHECK(show_purchase_references IN (0, 1)),
    show_processing_summary INTEGER NOT NULL DEFAULT 1 CHECK(show_processing_summary IN (0, 1)),
    show_weight_summary INTEGER NOT NULL DEFAULT 1 CHECK(show_weight_summary IN (0, 1)),
    show_asset_list INTEGER NOT NULL DEFAULT 1 CHECK(show_asset_list IN (0, 1)),
    show_sustainability INTEGER NOT NULL DEFAULT 0 CHECK(show_sustainability IN (0, 1)),
    sustainability_statement TEXT,
    signature_title TEXT NOT NULL DEFAULT 'Authorized Signatory',
    logo_path TEXT,
    header_text TEXT,
    footer_text TEXT,
    page_layout TEXT NOT NULL DEFAULT 'A4_PORTRAIT',
    margin_top REAL NOT NULL DEFAULT 36.0,
    margin_bottom REAL NOT NULL DEFAULT 36.0,
    margin_left REAL NOT NULL DEFAULT 36.0,
    margin_right REAL NOT NULL DEFAULT 36.0,
    show_gst INTEGER NOT NULL DEFAULT 1 CHECK(show_gst IN (0, 1)),
    show_cin INTEGER NOT NULL DEFAULT 1 CHECK(show_cin IN (0, 1)),
    show_pan INTEGER NOT NULL DEFAULT 1 CHECK(show_pan IN (0, 1)),
    show_pcb INTEGER NOT NULL DEFAULT 1 CHECK(show_pcb IN (0, 1)),
    show_iso INTEGER NOT NULL DEFAULT 0 CHECK(show_iso IN (0, 1)),
    show_r2 INTEGER NOT NULL DEFAULT 0 CHECK(show_r2 IN (0, 1)),
    show_estewards INTEGER NOT NULL DEFAULT 0 CHECK(show_estewards IN (0, 1)),
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('DRAFT', 'ACTIVE', 'ARCHIVED')),
    version INTEGER NOT NULL DEFAULT 1,
    created_by TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS certificate (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    certificate_number TEXT NOT NULL UNIQUE,
    certificate_type TEXT NOT NULL CHECK(certificate_type IN ('RECYCLING', 'DECOMPOSITION', 'REFURBISHMENT', 'COMBINED')),
    customer_id INTEGER NOT NULL REFERENCES party(id),
    status TEXT NOT NULL DEFAULT 'DRAFT' CHECK(status IN ('DRAFT', 'PREVIEW', 'GENERATED', 'LOCKED', 'ARCHIVED', 'CANCELLED', 'SUPERSEDED')),
    template_key TEXT NOT NULL REFERENCES certificate_template(template_key),
    template_version INTEGER NOT NULL DEFAULT 1,
    generation_date TEXT,
    version_number INTEGER NOT NULL DEFAULT 1,
    superseded_certificate_id INTEGER REFERENCES certificate(id),
    replaces_certificate_id INTEGER REFERENCES certificate(id),
    verification_uuid TEXT NOT NULL,
    digital_signature_hash TEXT,
    signed_by TEXT,
    signed_at TEXT,
    verification_hash TEXT,
    remarks TEXT,
    cancellation_reason TEXT,
    cancelled_by TEXT,
    cancelled_at TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS certificate_pdf (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    certificate_id INTEGER NOT NULL REFERENCES certificate(id) ON DELETE CASCADE,
    pdf_path TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    generated_by TEXT NOT NULL,
    generated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    checksum TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE'
);

CREATE TABLE IF NOT EXISTS certificate_processing (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    certificate_id INTEGER NOT NULL REFERENCES certificate(id) ON DELETE CASCADE,
    processing_job_id INTEGER NOT NULL REFERENCES processing_job(id),
    FOREIGN KEY (certificate_id) REFERENCES certificate(id) ON DELETE CASCADE,
    FOREIGN KEY (processing_job_id) REFERENCES processing_job(id)
);

CREATE TABLE IF NOT EXISTS certificate_purchase (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    certificate_id INTEGER NOT NULL REFERENCES certificate(id) ON DELETE CASCADE,
    purchase_id INTEGER NOT NULL REFERENCES purchase_invoice(id),
    FOREIGN KEY (certificate_id) REFERENCES certificate(id) ON DELETE CASCADE,
    FOREIGN KEY (purchase_id) REFERENCES purchase_invoice(id)
);

CREATE TABLE IF NOT EXISTS certificate_asset_attachment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    certificate_id INTEGER NOT NULL REFERENCES certificate(id) ON DELETE CASCADE,
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_type TEXT NOT NULL,
    uploaded_by TEXT NOT NULL,
    uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (certificate_id) REFERENCES certificate(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS certificate_activity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    certificate_id INTEGER NOT NULL REFERENCES certificate(id) ON DELETE CASCADE,
    action TEXT NOT NULL,
    performed_by TEXT NOT NULL,
    remarks TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (certificate_id) REFERENCES certificate(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_certificate_status ON certificate(status);
CREATE INDEX IF NOT EXISTS idx_certificate_number ON certificate(certificate_number);
CREATE INDEX IF NOT EXISTS idx_certificate_customer ON certificate(customer_id);
CREATE INDEX IF NOT EXISTS idx_certificate_pdf_cert ON certificate_pdf(certificate_id);
CREATE INDEX IF NOT EXISTS idx_cert_processing_cert ON certificate_processing(certificate_id);
CREATE INDEX IF NOT EXISTS idx_cert_purchase_cert ON certificate_purchase(certificate_id);

-- Insert Default Templates
INSERT OR IGNORE INTO certificate_template (template_key, template_name, title, declaration_text, created_by)
VALUES ('STANDARD', 'Standard Recycling Template', 'CERTIFICATE OF RECYCLING', 'This certifies that all electronic waste received from the customer has been responsibly recycled and processed in accordance with national environment conservation standards.', 'System');

INSERT OR IGNORE INTO certificate_template (template_key, template_name, title, declaration_text, created_by)
VALUES ('CORPORATE', 'Corporate Compliance Template', 'CERTIFICATE OF ENVIRONMENTAL COMPLIANCE', 'This certifies that e-waste equipment received from the corporate client has been safely cataloged, dismantled, and processed. Data sanitation has been certified on all storage media.', 'System');

INSERT OR IGNORE INTO certificate_template (template_key, template_name, title, declaration_text, created_by)
VALUES ('GOVERNMENT', 'Government Audit Template', 'OFFICIAL RECYCLING & DISPOSAL CERTIFICATE', 'This official certificate verifies that public-sector asset items received have been fully processed and recycled in compliance with current government pollution control board standards.', 'System');

INSERT OR IGNORE INTO certificate_template (template_key, template_name, title, declaration_text, created_by)
VALUES ('REFURBISHMENT', 'Refurbishment Certificate Template', 'CERTIFICATE OF REFURBISHMENT', 'This certifies that the electronic devices and items listed herein have been successfully inspected, cleaned, repaired, and refurbished for secondary use.', 'System');
