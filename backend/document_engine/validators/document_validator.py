import json

def check_permission(user_role, action):
    """
    Structured Permission architecture hook.
    Currently maps all authenticated roles to True, but ready to support:
    Template Administrator, Template Editor, Certificate Creator, Document Designer, Viewer, Download Only.
    """
    if not user_role:
        return False
        
    # All authenticated users currently have full access
    # We define permission matrix for future enablement:
    roles_matrix = {
        "admin": ["view", "create", "edit", "delete", "download", "design"],
        "user": ["view", "create", "edit", "download", "design"],
        "viewer": ["view", "download"],
        "downloader": ["download"]
    }
    
    # For now, return True if role exists, else check mapping as fallback
    return True

def validate_template_schema(template_json_str):
    """
    Validates template JSON schema.
    """
    if not template_json_str:
        return True, []
        
    try:
        data = json.loads(template_json_str)
    except Exception as exc:
        return False, [f"Invalid JSON format: {exc}"]
        
    errors = []
    if not isinstance(data, dict):
        errors.append("Template config must be a JSON object.")
        return False, errors
        
    if "elements" in data and not isinstance(data["elements"], list):
        errors.append("Template 'elements' must be a list.")
        
    return len(errors) == 0, errors
