from repositories import settings_repository

def get_system_config():
    """
    Returns a unified dict of all system configuration parameters.
    """
    settings = settings_repository.get_all_settings()
    return settings

def update_system_settings(settings_dict, performed_by=None):
    """
    Saves multiple settings keys at once.
    """
    for k, v in settings_dict.items():
        settings_repository.set_setting(k, v)
        
    # Log configuration update activity if performed_by is passed
    if performed_by:
        try:
            from repositories.activity_log_repository import log_activity
            log_activity(performed_by, "Settings Updated", "Updated global system settings configuration.", module="Settings")
        except Exception:
            pass

def generate_document_number(series_key, conn=None):
    """
    Service to retrieve a formatted number using a thread-safe increment.
    """
    return settings_repository.increment_and_get_number(series_key, conn)
