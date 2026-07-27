import json
from typing import Dict, Any, List, Optional
from backend.database import get_connection
from backend.modules.documents.providers.storage_provider import StorageProvider
from backend.modules.documents.providers.local_storage_provider import LocalStorageProvider
from backend.modules.documents.providers.s3_storage_provider import AWSS3StorageProvider

class StorageProviderManager:
    """Centralized Storage Provider Manager and Storage Policy Routing Engine for EDMS."""

    def __init__(self):
        self._provider_cache = {}

    def get_provider_by_id(self, provider_id: int) -> StorageProvider:
        """Returns storage provider instance by database provider_id."""
        if provider_id in self._provider_cache:
            return self._provider_cache[provider_id]

        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM storage_providers WHERE id = ?", (provider_id,))
            row = cursor.fetchone()
            if not row:
                # Default to LocalStorageProvider
                return LocalStorageProvider()

            p_dict = dict(row)
            key = p_dict['provider_key'].lower()
            cfg = json.loads(p_dict['config_json'] or '{}')

            if key == 's3':
                inst = AWSS3StorageProvider(cfg)
            else:
                inst = LocalStorageProvider()

            self._provider_cache[provider_id] = inst
            return inst
        finally:
            conn.close()

    def resolve_provider_for_upload(self, scope: str = 'COMPANY') -> Dict[str, Any]:
        """Resolves target storage provider and ID using storage_routing_policies."""
        scope_clean = scope.upper().strip()
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT srp.*, sp.provider_key, sp.provider_name
                FROM storage_routing_policies srp
                JOIN storage_providers sp ON srp.target_provider_id = sp.id
                WHERE srp.scope = ? AND srp.is_active = 1
                LIMIT 1
            """, (scope_clean,))
            policy = cursor.fetchone()

            if policy:
                p_dict = dict(policy)
                provider_id = p_dict['target_provider_id']
            else:
                provider_id = 1
                p_dict = {"scope": scope_clean, "target_provider_id": 1, "provider_key": "local", "provider_name": "Local Storage Provider"}

            inst = self.get_provider_by_id(provider_id)
            return {
                "provider_id": provider_id,
                "provider_instance": inst,
                "policy": p_dict
            }
        finally:
            conn.close()

    def get_all_providers_status(self) -> List[Dict[str, Any]]:
        """Returns list of all configured storage providers with health status."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM storage_providers ORDER BY id ASC")
            providers = [dict(r) for r in cursor.fetchall()]

            for p in providers:
                inst = self.get_provider_by_id(p['id'])
                p['health'] = inst.health_check()
                cursor.execute("SELECT COUNT(*) as cnt, COALESCE(SUM(size_bytes),0) as total FROM documents WHERE storage_provider_id = ? AND status = 'ACTIVE'", (p['id'],))
                usage = cursor.fetchone()
                p['documents_count'] = usage['cnt']
                p['storage_used_mb'] = round(usage['total'] / (1024 * 1024), 2)

            return providers
        finally:
            conn.close()

    def get_routing_policies(self) -> List[Dict[str, Any]]:
        """Lists active storage routing policies."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT srp.*, sp.provider_name, sp.provider_key
                FROM storage_routing_policies srp
                JOIN storage_providers sp ON srp.target_provider_id = sp.id
                ORDER BY srp.id ASC
            """)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def update_routing_policy(self, scope: str, target_provider_id: int) -> bool:
        """Updates storage routing policy for a given scope."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO storage_routing_policies (scope, target_provider_id, is_active)
                VALUES (?, ?, 1)
                ON CONFLICT(scope) DO UPDATE SET target_provider_id = excluded.target_provider_id, is_active = 1
            """, (scope.upper(), target_provider_id))
            conn.commit()
            return True
        finally:
            conn.close()
