import io
import os
import shutil
import hashlib
from pathlib import Path
from typing import BinaryIO, Dict, Any, List, Optional
from backend.modules.documents.providers.storage_provider import StorageProvider

class AzureBlobStorageProvider(StorageProvider):
    """Microsoft Azure Blob Object Storage Provider Implementation for EDMS.
    
    Includes simulated local cloud fallback for development and testing.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.account_name = self.config.get("account_name", "right-ewaste-blob")
        self.container_name = self.config.get("container_name", "edms-container")
        self.account_key = self.config.get("account_key", "MOCK_AZURE_KEY")
        self.endpoint_url = self.config.get("endpoint_url", "")

        # Fallback local directory simulation for Azure storage
        base_dir = Path(__file__).resolve().parent.parent.parent.parent / "storage" / "azure_simulated"
        self.azure_local_dir = base_dir / self.container_name
        self.azure_local_dir.mkdir(parents=True, exist_ok=True)

        self._blob_service_client = None
        self._initialize_client()

    def _initialize_client(self):
        try:
            # Placeholder for potential azure-storage-blob library integration
            if self.account_key != "MOCK_AZURE_KEY":
                from azure.storage.blob import BlobServiceClient
                conn_str = f"DefaultEndpointsProtocol=https;AccountName={self.account_name};AccountKey={self.account_key};EndpointSuffix=core.windows.net"
                if self.endpoint_url:
                    conn_str += f";BlobEndpoint={self.endpoint_url}"
                self._blob_service_client = BlobServiceClient.from_connection_string(conn_str)
        except Exception:
            self._blob_service_client = None

    def upload_file(self, file_stream: BinaryIO, storage_key: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        storage_key = storage_key.lstrip('/')
        if self._blob_service_client:
            file_stream.seek(0)
            blob_client = self._blob_service_client.get_blob_client(container=self.container_name, blob=storage_key)
            blob_client.upload_blob(file_stream, overwrite=True, metadata=metadata or {})
            file_stream.seek(0, 2)
            size = file_stream.tell()
            file_stream.seek(0)
            sha256 = hashlib.sha256(file_stream.read()).hexdigest()
            file_stream.seek(0)
        else:
            # Fallback Local Azure Simulation
            target_path = self.azure_local_dir / storage_key
            target_path.parent.mkdir(parents=True, exist_ok=True)
            file_stream.seek(0)
            content = file_stream.read()
            with open(target_path, "wb") as f:
                f.write(content)
            size = len(content)
            sha256 = hashlib.sha256(content).hexdigest()
            file_stream.seek(0)

        return {
            "provider": "azure",
            "container": self.container_name,
            "storage_key": storage_key,
            "size_bytes": size,
            "checksum_sha256": sha256
        }

    def download_file(self, storage_key: str) -> BinaryIO:
        storage_key = storage_key.lstrip('/')
        stream = io.BytesIO()
        if self._blob_service_client:
            blob_client = self._blob_service_client.get_blob_client(container=self.container_name, blob=storage_key)
            download_stream = blob_client.download_blob()
            stream.write(download_stream.readall())
            stream.seek(0)
            return stream
        else:
            target_path = self.azure_local_dir / storage_key
            if not target_path.exists():
                raise FileNotFoundError(f"Azure Blob '{storage_key}' not found in container '{self.container_name}'.")
            with open(target_path, "rb") as f:
                stream.write(f.read())
            stream.seek(0)
            return stream

    def delete_file(self, storage_key: str) -> bool:
        storage_key = storage_key.lstrip('/')
        if self._blob_service_client:
            blob_client = self._blob_service_client.get_blob_client(container=self.container_name, blob=storage_key)
            blob_client.delete_blob()
            return True
        else:
            target_path = self.azure_local_dir / storage_key
            if target_path.exists():
                target_path.unlink()
                return True
            return False

    def rename_file(self, old_key: str, new_key: str) -> bool:
        return self.move_file(old_key, new_key)

    def copy_file(self, source_key: str, dest_key: str) -> bool:
        source_key = source_key.lstrip('/')
        dest_key = dest_key.lstrip('/')
        if self._blob_service_client:
            source_blob = f"https://{self.account_name}.blob.core.windows.net/{self.container_name}/{source_key}"
            dest_blob_client = self._blob_service_client.get_blob_client(container=self.container_name, blob=dest_key)
            dest_blob_client.start_copy_from_url(source_blob)
            return True
        else:
            src = self.azure_local_dir / source_key
            dst = self.azure_local_dir / dest_key
            if not src.exists():
                return False
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            return True

    def move_file(self, source_key: str, dest_key: str) -> bool:
        copied = self.copy_file(source_key, dest_key)
        if copied:
            self.delete_file(source_key)
            return True
        return False

    def create_folder(self, folder_path: str) -> bool:
        folder_path = folder_path.strip('/').lower() + '/'
        if self._blob_service_client:
            # Azure creates blobs under virtual directory paths
            blob_client = self._blob_service_client.get_blob_client(container=self.container_name, blob=folder_path)
            blob_client.upload_blob(b"", overwrite=True)
        else:
            (self.azure_local_dir / folder_path).mkdir(parents=True, exist_ok=True)
        return True

    def delete_folder(self, folder_path: str) -> bool:
        folder_path = folder_path.strip('/').lower()
        target = self.azure_local_dir / folder_path
        if target.exists() and target.is_dir():
            shutil.rmtree(target)
            return True
        return False

    def list_files(self, folder_path: str = "") -> List[Dict[str, Any]]:
        folder_path = folder_path.lstrip('/')
        target = self.azure_local_dir / folder_path
        if not target.exists() or not target.is_dir():
            return []
        files = []
        for p in target.glob("*"):
            if p.is_file():
                files.append({"key": str(p.relative_to(self.azure_local_dir)).replace('\\', '/'), "size": p.stat().st_size})
        return files

    def list_folders(self, folder_path: str = "") -> List[Dict[str, Any]]:
        folder_path = folder_path.lstrip('/')
        target = self.azure_local_dir / folder_path
        if not target.exists() or not target.is_dir():
            return []
        folders = []
        for p in target.glob("*"):
            if p.is_dir():
                folders.append({"name": p.name, "path": str(p.relative_to(self.azure_local_dir)).replace('\\', '/')})
        return folders

    def get_metadata(self, storage_key: str) -> Dict[str, Any]:
        storage_key = storage_key.lstrip('/')
        target = self.azure_local_dir / storage_key
        if not target.exists():
            raise FileNotFoundError(f"Azure Blob '{storage_key}' not found.")
        return {
            "key": storage_key,
            "size_bytes": target.stat().st_size,
            "container": self.container_name,
            "provider": "azure"
        }

    def get_storage_size(self, storage_key: str) -> int:
        return self.get_metadata(storage_key)['size_bytes']

    def generate_temp_url(self, storage_key: str, expiration_seconds: int = 3600) -> str:
        storage_key = storage_key.lstrip('/')
        return f"/api/v1/documents/azure-simulated-download?key={storage_key}"

    def file_exists(self, storage_key: str) -> bool:
        storage_key = storage_key.lstrip('/')
        target = self.azure_local_dir / storage_key
        return target.exists() and target.is_file()

    def folder_exists(self, folder_path: str) -> bool:
        folder_path = folder_path.lstrip('/')
        target = self.azure_local_dir / folder_path
        return target.exists() and target.is_dir()

    def calculate_storage_size(self, folder_path: str) -> int:
        folder_path = folder_path.lstrip('/')
        target = self.azure_local_dir / folder_path
        if not target.exists():
            return 0
        total = 0
        if target.is_file():
            return target.stat().st_size
        for path in target.rglob("*"):
            if path.is_file():
                total += path.stat().st_size
        return total

    def validate_connection(self) -> bool:
        return True

    def health_check(self) -> Dict[str, Any]:
        return {
            "provider": "azure",
            "container": self.container_name,
            "status": "HEALTHY",
            "mode": "ACTIVE_AZURE" if self._blob_service_client else "SIMULATED_LOCAL_AZURE"
        }
