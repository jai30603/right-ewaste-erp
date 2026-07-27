import re
import os
from typing import Dict, Any, Tuple

DEFAULT_MAX_SIZE_BYTES = 50 * 1024 * 1024 # 50 MB
ALLOWED_EXTENSIONS = {
    'pdf', 'doc', 'docx', 'xls', 'xlsx', 'csv',
    'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg',
    'txt', 'json', 'xml', 'zip', 'rar', '7z'
}

DANGEROUS_EXTENSIONS = {'exe', 'bat', 'cmd', 'sh', 'php', 'py', 'js', 'vbs', 'scr', 'dll'}

class DocumentValidator:
    """Centralized File Validation Rules for EDMS Uploads."""

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitizes user-supplied filename to prevent path injection."""
        base_name = os.path.basename(filename)
        clean_name = re.sub(r'[^a-zA-Z0-9_.\-\s]', '_', base_name).strip()
        return clean_name or "unnamed_document"

    @classmethod
    def validate_upload(cls, filename: str, size_bytes: int, max_size_bytes: int = DEFAULT_MAX_SIZE_BYTES) -> Tuple[bool, str]:
        """Validates file upload parameters against extension, size, and danger checks."""
        if not filename or not filename.strip():
            return False, "File name cannot be empty."

        clean_name = cls.sanitize_filename(filename)
        parts = clean_name.rsplit('.', 1)
        ext = parts[1].lower() if len(parts) > 1 else ''

        if not ext:
            return False, "File must have a valid extension."

        if ext in DANGEROUS_EXTENSIONS:
            return False, f"Security Violation: Executable extension '.{ext}' is strictly forbidden."

        if ext not in ALLOWED_EXTENSIONS:
            return False, f"Unsupported file type '.{ext}'. Allowed types: {', '.join(sorted(ALLOWED_EXTENSIONS))}"

        if size_bytes < 0:
            return False, "Cannot upload file with negative size."

        if size_bytes > max_size_bytes:
            max_mb = max_size_bytes / (1024 * 1024)
            return False, f"File size exceeds maximum allowed limit of {max_mb:.0f} MB."

        return True, "Validation successful."
