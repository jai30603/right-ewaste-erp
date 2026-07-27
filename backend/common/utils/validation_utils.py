"""
Validation Utilities
Placeholder for reusable validation logic.
"""

def is_valid_phone(phone_str):
    if not phone_str:
        return False
    return phone_str.strip().isdigit()

def is_valid_email(email_str):
    if not email_str:
        return False
    return "@" in email_str.strip()
