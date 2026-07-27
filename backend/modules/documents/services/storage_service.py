import json
import base64
from typing import BinaryIO, Dict, Any, List, Optional
from backend.database import get_connection
from backend.modules.documents.providers.storage_provider import StorageProvider
from backend.modules.documents.providers.local_storage_provider import LocalStorageProvider
from backend.modules.documents.providers.s3_storage_provider import AWSS3StorageProvider
from backend.modules.documents.providers.azure_storage_provider import AzureBlobStorageProvider
from backend.modules.documents.providers.gcs_storage_provider import GCSStorageProvider

XOR_KEY = b"RIGHT_EWASTE_SECRET"

def xor_crypt(data: str) -> str:
    """XOR encryption helper for simple database credential obfuscation."""
    data_bytes = data.encode('utf-8')
    crypt_bytes = bytes([b ^ XOR_KEY[i % len(XOR_KEY)] for i, b in enumerate(data_bytes)])
    return base64.b64encode(crypt_bytes).decode('utf-8')

def xor_decrypt(data_b64: str) -> str:
    """XOR decryption helper for database credential deobfuscation."""
    try:
        crypt_bytes = base64.b64decode(data_b64.encode('utf-8'))
        plain_bytes = bytes([b ^ XOR_KEY[i % len(XOR_KEY)] for i, b in enumerate(crypt_bytes)])
        return plain_bytes.decode('utf-8')
    except Exception:
        return "{}"

class EDMSStorageService(StorageProvider):
    """Centralized, provider-independent storage router for My Drive, Company, and Chat Files."""

    def __init__(self):
        self._fallback_provider = LocalStorageProvider()

    def get_active_provider(self) -> StorageProvider:
        """Retrieves and instantiates the active cloud storage provider, falling back to Local."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT provider_key, config_json 
                FROM storage_providers 
                WHERE is_active = 1 LIMIT 1
            """)
            row = cursor.fetchone()
            if not row:
                return self._fallback_provider

            pkey, crypt_json = row
            try:
                decrypted_str = xor_decrypt(crypt_json)
                config = json.loads(decrypted_str)
            except Exception:
                config = {}

            if pkey in ['aws_s3', 's3']:
                # AWS S3 Storage Provider
                aws_config = {
                    "bucket": config.get("bucket_name", "right-ewaste-docs"),
                    "region": config.get("aws_region", "ap-south-1"),
                    "access_key": config.get("aws_access_key_id", "MOCK_KEY"),
                    "secret_key": config.get("aws_secret_access_key", "MOCK_SECRET"),
                }
                return AWSS3StorageProvider(config=aws_config)
            elif pkey == 'azure_blob':
                # Azure Blob Storage Provider
                return AzureBlobStorageProvider(config=config)
            elif pkey == 'gcs':
                # Google Cloud Storage Provider
                return GCSStorageProvider(config=config)
            else:
                return self._fallback_provider
        except Exception as e:
            print(f"Error loading active storage provider: {e}")
            return self._fallback_provider
        finally:
            conn.close()

    # StorageProvider Interface implementation
    def upload_file(self, file_stream: BinaryIO, storage_key: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self.get_active_provider().upload_file(file_stream, storage_key, metadata)

    def download_file(self, storage_key: str) -> BinaryIO:
        return self.get_active_provider().download_file(storage_key)

    def delete_file(self, storage_key: str) -> bool:
        return self.get_active_provider().delete_file(storage_key)

    def rename_file(self, old_key: str, new_key: str) -> bool:
        return self.get_active_provider().rename_file(old_key, new_key)

    def move_file(self, source_key: str, destination_key: str) -> bool:
        return self.get_active_provider().move_file(source_key, destination_key)

    def copy_file(self, source_key: str, destination_key: str) -> bool:
        return self.get_active_provider().copy_file(source_key, destination_key)

    def create_folder(self, folder_path: str) -> bool:
        return self.get_active_provider().create_folder(folder_path)

    def delete_folder(self, folder_path: str) -> bool:
        return self.get_active_provider().delete_folder(folder_path)

    def file_exists(self, storage_key: str) -> bool:
        return self.get_active_provider().file_exists(storage_key)

    def folder_exists(self, folder_path: str) -> bool:
        return self.get_active_provider().folder_exists(folder_path)

    def list_files(self, folder_path: str = "") -> List[Dict[str, Any]]:
        return self.get_active_provider().list_files(folder_path)

    def list_folders(self, folder_path: str = "") -> List[Dict[str, Any]]:
        return self.get_active_provider().list_folders(folder_path)

    def get_metadata(self, storage_key: str) -> Dict[str, Any]:
        return self.get_active_provider().get_metadata(storage_key)

    def get_storage_size(self, storage_key: str) -> int:
        return self.get_active_provider().get_storage_size(storage_key)

    def generate_temp_url(self, storage_key: str, expiration_seconds: int = 3600) -> str:
        return self.get_active_provider().generate_temp_url(storage_key, expiration_seconds)

    def calculate_storage_size(self, folder_path: str) -> int:
        return self.get_active_provider().calculate_storage_size(folder_path)

    def health_check(self) -> Dict[str, Any]:
        return self.get_active_provider().health_check()
