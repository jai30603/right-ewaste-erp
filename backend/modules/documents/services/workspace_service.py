import json
import sqlite3
from datetime import datetime
from backend.database import get_connection
from backend.modules.documents.services.storage_service import EDMSStorageService, xor_decrypt
from backend.modules.documents.providers.s3_storage_provider import AWSS3StorageProvider
from backend.modules.documents.providers.azure_storage_provider import AzureBlobStorageProvider
from backend.modules.documents.providers.gcs_storage_provider import GCSStorageProvider

class EDMSWorkspaceService:
    """Service to handle EDMS workspace initialization, user provisioning, and health monitoring."""

    def get_provider_by_id(self, provider_id: int):
        """Instantiates a storage provider class by its ID."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT provider_key, config_json FROM storage_providers WHERE id = ?", (provider_id,))
            row = cursor.fetchone()
            if not row:
                return None
            pkey, crypt_json = row
            try:
                decrypted_str = xor_decrypt(crypt_json)
                config = json.loads(decrypted_str)
            except Exception:
                config = {}

            if pkey in ['aws_s3', 's3']:
                aws_config = {
                    "bucket": config.get("bucket_name", "right-ewaste-docs"),
                    "region": config.get("aws_region", "ap-south-1"),
                    "access_key": config.get("aws_access_key_id", "MOCK_KEY"),
                    "secret_key": config.get("aws_secret_access_key", "MOCK_SECRET"),
                }
                return AWSS3StorageProvider(config=aws_config)
            elif pkey == 'azure_blob':
                return AzureBlobStorageProvider(config=config)
            elif pkey == 'gcs':
                return GCSStorageProvider(config=config)
            return None
        finally:
            conn.close()

    def initialize_workspace(self, provider_id: int) -> bool:
        """Configures root company/user directories and provisions storage folders for all existing users."""
        provider = self.get_provider_by_id(provider_id)
        if not provider:
            return False

        # Validate connection first
        try:
            is_valid = provider.validate_connection()
            if not is_valid:
                raise ValueError("Credentials test failed during validation checks.")
        except Exception as e:
            self._update_init_status(provider_id, "FAILED")
            self._update_health_error(provider_id, str(e))
            return False

        try:
            # 1. Create root logical folders
            provider.create_folder("Company")
            provider.create_folder("Users")

            # 2. Synchronize existing users
            self.provision_existing_users(provider_id, provider)

            # 3. Log success
            self._update_init_status(provider_id, "SUCCESS")
            self.sync_provider_health(provider_id, provider)
            return True
        except Exception as e:
            self._update_init_status(provider_id, "FAILED")
            self._update_health_error(provider_id, str(e))
            return False

    def provision_existing_users(self, provider_id: int, provider=None):
        """Automatically provisions logical folders and active cloud directories for all users."""
        if not provider:
            provider = self.get_provider_by_id(provider_id)
        if not provider:
            return

        conn = get_connection()
        try:
            cursor = conn.cursor()
            # Fetch all users
            cursor.execute("SELECT id, username, uuid FROM users WHERE status = 'ACTIVE'")
            users = cursor.fetchall()
            
            for uid, uname, u_uuid in users:
                if not u_uuid:
                    import uuid
                    u_uuid = str(uuid.uuid4())
                    cursor.execute("UPDATE users SET uuid = ? WHERE id = ?", (u_uuid, uid))
                
                # Check or create root folders
                user_path = f"/users/{u_uuid}"
                user_path = f"/users/{u_uuid}"
                chatfiles_path = f"{user_path}/chatfiles"
                
                # Create logical entries
                cursor.execute("SELECT id FROM folders WHERE path = ? AND owner_user_id = ?", (user_path, uid))
                if not cursor.fetchone():
                    import uuid as uuid_gen
                    cursor.execute("""
                        INSERT INTO folders (uuid, name, parent_folder_id, folder_type, owner_user_id, path, status, created_by, repository_id)
                        VALUES (?, 'My Drive', NULL, 'USER', ?, ?, 'ACTIVE', ?, 1)
                    """, (str(uuid_gen.uuid4()), uid, user_path, uid))

                cursor.execute("SELECT id FROM folders WHERE path = ? AND owner_user_id = ?", (chatfiles_path, uid))
                if not cursor.fetchone():
                    import uuid as uuid_gen
                    cursor.execute("""
                        INSERT INTO folders (uuid, name, parent_folder_id, folder_type, owner_user_id, path, status, created_by, repository_id)
                        VALUES (?, 'Chat Files', NULL, 'USER', ?, ?, 'ACTIVE', ?, 3)
                    """, (str(uuid_gen.uuid4()), uid, chatfiles_path, uid))

                # Create user storage quotas
                cursor.execute("INSERT OR IGNORE INTO user_storage (user_id) VALUES (?)", (uid,))
                cursor.execute("INSERT OR IGNORE INTO storage_usage (user_id) VALUES (?)", (uid,))

                # Create cloud directories physically
                provider.create_folder(f"Users/{u_uuid}/My Drive")
                provider.create_folder(f"Users/{u_uuid}/Chat Files")
            
            conn.commit()
        finally:
            conn.close()

    def sync_provider_health(self, provider_id: int, provider=None):
        """Monitors and updates connection, file metrics, and storage stats in storage_health."""
        if not provider:
            provider = self.get_provider_by_id(provider_id)
        if not provider:
            return

        conn = get_connection()
        try:
            cursor = conn.cursor()
            
            # Fetch files/folders statistics
            health = provider.health_check()
            status = health.get("status", "HEALTHY")
            
            # Count logical records
            cursor.execute("SELECT COUNT(*) FROM documents WHERE repository_id = 1 OR repository_id = 2")
            total_files = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM folders WHERE repository_id = 1 OR repository_id = 2")
            total_folders = cursor.fetchone()[0]
            
            cursor.execute("SELECT COALESCE(SUM(size_bytes), 0) FROM documents WHERE repository_id = 1 OR repository_id = 2")
            total_size = cursor.fetchone()[0]

            cursor.execute("""
                INSERT INTO storage_health (
                    provider_id, connection_status, bucket_availability, last_successful_connection, 
                    last_error, total_files, total_folders, storage_usage_bytes, updated_at
                ) VALUES (?, 'CONNECTED', 1, ?, NULL, ?, ?, ?, ?)
                ON CONFLICT(provider_id) DO UPDATE SET
                    connection_status = 'CONNECTED',
                    bucket_availability = 1,
                    last_successful_connection = excluded.last_successful_connection,
                    last_error = NULL,
                    total_files = excluded.total_files,
                    total_folders = excluded.total_folders,
                    storage_usage_bytes = excluded.storage_usage_bytes,
                    updated_at = excluded.updated_at
            """, (provider_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), total_files, total_folders, total_size, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            
            # Sync to storage_providers table as well
            cursor.execute("""
                UPDATE storage_providers 
                SET status = 'CONNECTED', health_status = 'HEALTHY', last_synchronization = ?, updated_at = ?
                WHERE id = ?
            """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), provider_id))
            
            conn.commit()
        finally:
            conn.close()

    def _update_init_status(self, provider_id: int, status: str):
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO workspace_initialization (provider_id, initialized_at, status)
                VALUES (?, ?, ?)
                ON CONFLICT(provider_id) DO UPDATE SET
                    initialized_at = excluded.initialized_at,
                    status = excluded.status
            """, (provider_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), status))
            conn.commit()
        finally:
            conn.close()

    def _update_health_error(self, provider_id: int, error_msg: str):
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO storage_health (provider_id, connection_status, bucket_availability, last_error, updated_at)
                VALUES (?, 'ERROR', 0, ?, ?)
                ON CONFLICT(provider_id) DO UPDATE SET
                    connection_status = 'ERROR',
                    bucket_availability = 0,
                    last_error = excluded.last_error,
                    updated_at = excluded.updated_at
            """, (provider_id, error_msg, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            
            cursor.execute("""
                UPDATE storage_providers 
                SET status = 'ERROR', health_status = 'UNHEALTHY', updated_at = ?
                WHERE id = ?
            """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), provider_id))
            
            conn.commit()
        finally:
            conn.close()
