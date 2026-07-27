import time
import hashlib
import json
import threading

# Thread-safe in-memory cache dictionary
# Structure: { cache_key: { "bytes": pdf_bytes, "expires_at": timestamp } }
_cache = {}
_cache_lock = threading.Lock()

def generate_key(template_key, template_version, purchase_id, template_json=None, custom_table_json=None):
    """
    Generates a unique cache key based on the rendering context.
    """
    hasher = hashlib.sha256()
    hasher.update(str(template_key).encode('utf-8'))
    hasher.update(str(template_version).encode('utf-8'))
    hasher.update(str(purchase_id).encode('utf-8'))
    
    # Optional layouts and tables snapshots
    if template_json:
        hasher.update(str(template_json).encode('utf-8'))
    if custom_table_json:
        hasher.update(str(custom_table_json).encode('utf-8'))
        
    return hasher.hexdigest()

def get(cache_key):
    """
    Retrieves transient PDF bytes from cache if still valid.
    """
    with _cache_lock:
        entry = _cache.get(cache_key)
        if not entry:
            return None
        
        # Check expiration
        if time.time() > entry["expires_at"]:
            del _cache[cache_key]
            return None
            
        return entry["bytes"]

def set_cache(cache_key, pdf_bytes, expire_seconds=900):
    """
    Stores PDF bytes in transient cache for standard expiration (default: 15 minutes).
    """
    with _cache_lock:
        _cache[cache_key] = {
            "bytes": pdf_bytes,
            "expires_at": time.time() + expire_seconds
        }

def clear():
    """
    Explicitly flushes the transient cache.
    """
    with _cache_lock:
        _cache.clear()

def clean_expired():
    """
    Performs memory cleanup of expired items.
    """
    now = time.time()
    with _cache_lock:
        expired_keys = [k for k, v in _cache.items() if now > v["expires_at"]]
        for k in expired_keys:
            del _cache[k]
