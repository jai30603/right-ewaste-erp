from document_engine.repositories import template_repository, document_repository
from document_engine.validators.document_validator import validate_template_schema

def load_template(template_key, version=None):
    return template_repository.get_template_by_key(template_key, version)

def get_all_templates():
    return template_repository.get_templates_list()

def clone_template(source_key, target_key, target_name, performed_by):
    """
    Clones template schema records to a new template series.
    """
    src = template_repository.get_template_by_key(source_key)
    if not src:
        raise ValueError(f"Source template '{source_key}' not found.")
        
    t_data = dict(src)
    t_data["template_key"] = target_key
    t_data["template_name"] = target_name
    t_data["version"] = 0  # Forces start from version 1 in save_template_version
    t_data["created_by"] = performed_by
    
    new_ver = template_repository.save_template_version(t_data)
    
    # Audit log cloning
    document_repository.insert_audit_log(
        user_name=performed_by,
        action="TEMPLATE_CLONED",
        entity_type="template",
        entity_id=target_key,
        previous_version=None,
        new_version=new_ver,
        details=f"Cloned template from '{source_key}' to '{target_key}'"
    )
    return new_ver

def save_template(t_data, performed_by):
    """
    Validates and saves a new template version in the library.
    """
    # Schema validation
    is_valid, errors = validate_template_schema(t_data.get("template_json"))
    if not is_valid:
        raise ValueError(f"Template JSON validation failed: {', '.join(errors)}")
        
    t_data["created_by"] = performed_by
    
    # Load previous version number for audit log tracking
    prev = template_repository.get_template_by_key(t_data["template_key"])
    prev_ver = prev["version"] if prev else None
    
    new_ver = template_repository.save_template_version(t_data)
    
    # Audit logging
    action = "TEMPLATE_CREATED" if prev_ver is None else "TEMPLATE_UPDATED"
    document_repository.insert_audit_log(
        user_name=performed_by,
        action=action,
        entity_type="template",
        entity_id=t_data["template_key"],
        previous_version=prev_ver,
        new_version=new_ver,
        details=f"Saved template '{t_data['template_name']}' version {new_ver}"
    )
    return new_ver
