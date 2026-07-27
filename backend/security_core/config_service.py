import logging
from database import get_connection

logger = logging.getLogger(__name__)

# In-memory config cache
_CONFIG_CACHE = {}

def get_config(key, default=None):
    """
    Retrieves system setting dynamically from database with in-memory caching.
    Falls back to business config module variables if not defined in database.
    """
    global _CONFIG_CACHE
    if key in _CONFIG_CACHE:
        return _CONFIG_CACHE[key]
        
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT setting_value FROM system_setting WHERE setting_key = ?", (key,))
        row = cursor.fetchone()
        if row:
            val = row[0]
            # Convert boolean string representations
            if val.lower() in ("true", "1", "yes", "on"):
                val = True
            elif val.lower() in ("false", "0", "no", "off"):
                val = False
            _CONFIG_CACHE[key] = val
            return val
    except Exception as e:
        logger.warning("Error fetching setting %s from database: %s", key, e)
    finally:
        conn.close()

    # Fallback to static business config if database is empty/missing
    try:
        from config import business
        if hasattr(business, key):
            val = getattr(business, key)
            _CONFIG_CACHE[key] = val
            return val
    except ImportError:
        pass

    # Global hardcoded defaults for security params if missing everywhere
    defaults = {
        "SESSION_TIMEOUT": 30, # minutes
        "PASSWORD_MIN_LENGTH": 6,
        "PASSWORD_EXPIRY_DAYS": 90,
        "MAX_FAILED_LOGIN": 5,
        "ALLOW_MULTIPLE_SESSIONS": True,
        "DEFAULT_THEME": "light",
        "DEFAULT_LANGUAGE": "en"
    }
    if key in defaults:
        _CONFIG_CACHE[key] = defaults[key]
        return defaults[key]

    return default

def clear_cache():
    """
    Flushes the in-memory settings cache.
    Call this whenever settings are updated in Settings Center.
    """
    global _CONFIG_CACHE
    _CONFIG_CACHE.clear()
