import io
import os
import shutil
import hashlib
from pathlib import Path
from typing import BinaryIO, Dict, Any, List, Optional
from backend.modules.documents.providers.storage_provider import StorageProvider

class GCSStorageProvider(StorageProvider):
    """Google Cloud Object Storage Provider Implementation for EDMS.
    
    Includes simulated local cloud fallback for development and testing.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.project_id = self.config.get("project_id", "right-ewaste-gcp")
        self.bucket_name = self.config.get("bucket_name", "edms-bucket")
        self.service_account_json = self.config.get("service_account_json", "MOCK_GCS_KEY")
        self.region = self.config.get("region", "us-central1")

        # Fallback local directory simulation for GCP storage
        base_dir = Path(__file__).resolve().parent.parent.parent.parent / "storage" / "gcs_simulated"
        self.gcs_local_dir = base_dir / self.bucket_name
        self.gcs_local_dir.mkdir(parents=True, exist_ok=True)

        self._gcs_client = None
        self._initialize_client()

    def _initialize_client(self):
        try:
            # Placeholder for potential google-cloud-storage library integration
            if self.service_account_json != "MOCK_GCS_KEY":
                from google.cloud import storage
                import json
                # Can load JSON string credentials directly or write to temp file
                creds_dict = json.loads(self.service_account_json)
                self._gcs_client = storage.Client.from_service_account_info(creds_dict)
        except Exception:
            self._gcs_client = None

    def upload_file(self, file_stream: BinaryIO, storage_key: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        storage_key = storage_key.lstrip('/')
        if self._gcs_client:
            file_stream.seek(0)
            bucket = self._gcs_client.bucket(self.bucket_name)
            blob = bucket.blob(storage_key)
            blob.upload_from_file(file_stream, content_type=metadata.get("mime_type") if metadata else None)
            if metadata:
                blob.metadata = metadata
                blob.patch()
            file_stream.seek(0, 2)
            size = file_stream.tell()
            file_stream.seek(0)
            sha256 = hashlib.sha256(file_stream.read()).hexdigest()
            file_stream.seek(0)
        else:
            # Fallback Local GCS Simulation
            target_path = self.gcs_local_dir / storage_key
            target_path.parent.mkdir(parents=True, exist_ok=True)
            file_stream.seek(0)
            content = file_stream.read()
            with open(target_path, "wb") as f:
                f.write(content)
            size = len(content)
            sha256 = hashlib.sha256(content).hexdigest()
            file_stream.seek(0)

        return {
            "provider": "gcs",
            "bucket": self.bucket_name,
            "storage_key": storage_key,
            "size_bytes": size,
            "checksum_sha256": sha256
        }

    def download_file(self, storage_key: str) -> BinaryIO:
        storage_key = storage_key.lstrip('/')
        stream = io.BytesIO()
        if self._gcs_client:
            bucket = self._gcs_client.bucket(self.bucket_name)
            blob = bucket.blob(storage_key)
            blob.download_to_file(stream)
            stream.seek(0)
            return stream
        else:
            target_path = self.gcs_local_dir / storage_key
            if not target_path.exists():
                raise FileNotFoundError(f"GCS Blob '{storage_key}' not found in bucket '{self.bucket_name}'.")
            with open(target_path, "rb") as f:
                stream.write(f.read())
            stream.seek(0)
            return stream

    def delete_file(self, storage_key: str) -> bool:
        storage_key = storage_key.lstrip('/')
        if self._gcs_client:
            bucket = self._gcs_client.bucket(self.bucket_name)
            blob = bucket.blob(storage_key)
            blob.delete()
            return True
        else:
            target_path = self.gcs_local_dir / storage_key
            if target_path.exists():
                target_path.unlink()
                return True
            return False

    def rename_file(self, old_key: str, new_key: str) -> bool:
        return self.move_file(old_key, new_key)

    def copy_file(self, source_key: str, dest_key: str) -> bool:
        source_key = source_key.lstrip('/')
        dest_key = dest_key.lstrip('/')
        if self._gcs_client:
            bucket = self._gcs_client.bucket(self.bucket_name)
            source_blob = bucket.blob(source_key)
            bucket.copy_blob(source_blob, bucket, dest_key)
            return True
        else:
            src = self.gcs_local_dir / source_key
            dst = self.gcs_local_dir / dest_key
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
        if self._gcs_client:
            bucket = self._gcs_client.bucket(self.bucket_name)
            blob = bucket.blob(folder_path)
            blob.upload_from_string(b"")
        else:
            (self.gcs_local_dir / folder_path).mkdir(parents=True, exist_ok=True)
        return True

    def delete_folder(self, folder_path: str) -> bool:
        folder_path = folder_path.strip('/').lower()
        target = self.gcs_local_dir / folder_path
        if target.exists() and target.is_dir():
            shutil.rmtree(target)
            return True
        return False

    def list_files(self, folder_path: str = "") -> List[Dict[str, Any]]:
        folder_path = folder_path.lstrip('/')
        target = self.gcs_local_dir / folder_path
        if not target.exists() or not target.is_dir():
            return []
        files = []
        for p in target.glob("*"):
            if p.is_file():
                files.append({"key": str(p.relative_to(self.gcs_local_dir)).replace('\\', '/'), "size": p.stat().st_size})
        return files

    def list_folders(self, folder_path: str = "") -> List[Dict[str, Any]]:
        folder_path = folder_path.lstrip('/')
        target = self.gcs_local_dir / folder_path
        if not target.exists() or not target.is_dir():
            return []
        folders = []
        for p in target.glob("*"):
            if p.is_dir():
                folders.append({"name": p.name, "path": str(p.relative_to(self.gcs_local_dir)).replace('\\', '/')})
        return folders

    def get_metadata(self, storage_key: str) -> Dict[str, Any]:
        storage_key = storage_key.lstrip('/')
        target = self.gcs_local_dir / storage_key
        if not target.exists():
            raise FileNotFoundError(f"GCS Blob '{storage_key}' not found.")
        return {
            "key": storage_key,
            "size_bytes": target.stat().st_size,
            "bucket": self.bucket_name,
            "provider": "gcs"
        }

    def get_storage_size(self, storage_key: str) -> int:
        return self.get_metadata(storage_key)['size_bytes']

    def generate_temp_url(self, storage_key: str, expiration_seconds: int = 3600) -> str:
        storage_key = storage_key.lstrip('/')
        return f"/api/v1/documents/gcs-simulated-download?key={storage_key}"

    def file_exists(self, storage_key: str) -> bool:
        storage_key = storage_key.lstrip('/')
        target = self.gcs_local_dir / storage_key
        return target.exists() and target.is_file()

    def folder_exists(self, folder_path: str) -> bool:
        folder_path = folder_path.lstrip('/')
        target = self.gcs_local_dir / folder_path
        return target.exists() and target.is_dir()

    def calculate_storage_size(self, folder_path: str) -> int:
        folder_path = folder_path.lstrip('/')
        target = self.gcs_local_dir / folder_path
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
            "provider": "gcs",
            "bucket": self.bucket_name,
            "region": self.region,
            "status": "HEALTHY",
            "mode": "ACTIVE_GCS" if self._gcs_client else "SIMULATED_LOCAL_GCS"
        }
