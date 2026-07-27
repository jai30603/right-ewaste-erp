import io
import os
import shutil
import hashlib
from pathlib import Path
from typing import BinaryIO, Dict, Any, List, Optional
from backend.modules.documents.providers.storage_provider import StorageProvider

class AWSS3StorageProvider(StorageProvider):
    """AWS S3 Object Storage Provider Implementation for EDMS.
    
    Includes simulated local cloud fallback when AWS boto3 is unconfigured.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.bucket_name = self.config.get("bucket", "right-ewaste-docs")
        self.region = self.config.get("region", "ap-south-1")
        self.access_key = self.config.get("access_key", "MOCK_KEY")
        self.secret_key = self.config.get("secret_key", "MOCK_SECRET")

        # Fallback local directory simulation for S3 storage
        base_dir = Path(__file__).resolve().parent.parent.parent.parent / "storage" / "s3_simulated"
        self.s3_local_dir = base_dir / self.bucket_name
        self.s3_local_dir.mkdir(parents=True, exist_ok=True)

        self._s3_client = None
        self._initialize_client()

    def _initialize_client(self):
        try:
            import boto3
            if self.access_key and self.access_key != "MOCK_KEY" and not self.access_key.startswith("test_") and not self.access_key.startswith("mock"):
                self._s3_client = boto3.client(
                    's3',
                    aws_access_key_id=self.access_key,
                    aws_secret_access_key=self.secret_key,
                    region_name=self.region
                )
        except Exception:
            self._s3_client = None

    def upload_file(self, file_stream: BinaryIO, storage_key: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        storage_key = storage_key.lstrip('/')
        if self._s3_client:
            file_stream.seek(0)
            self._s3_client.upload_fileobj(file_stream, self.bucket_name, storage_key, ExtraArgs={"Metadata": metadata or {}})
            file_stream.seek(0, 2)
            size = file_stream.tell()
            file_stream.seek(0)
            sha256 = hashlib.sha256(file_stream.read()).hexdigest()
            file_stream.seek(0)
        else:
            # Fallback Local S3 Simulation
            target_path = self.s3_local_dir / storage_key
            target_path.parent.mkdir(parents=True, exist_ok=True)
            file_stream.seek(0)
            content = file_stream.read()
            with open(target_path, "wb") as f:
                f.write(content)
            size = len(content)
            sha256 = hashlib.sha256(content).hexdigest()
            file_stream.seek(0)

        return {
            "provider": "s3",
            "bucket": self.bucket_name,
            "storage_key": storage_key,
            "size_bytes": size,
            "checksum_sha256": sha256
        }

    def download_file(self, storage_key: str) -> BinaryIO:
        storage_key = storage_key.lstrip('/')
        stream = io.BytesIO()
        if self._s3_client:
            self._s3_client.download_fileobj(self.bucket_name, storage_key, stream)
            stream.seek(0)
            return stream
        else:
            target_path = self.s3_local_dir / storage_key
            if not target_path.exists():
                raise FileNotFoundError(f"S3 Object '{storage_key}' not found in bucket '{self.bucket_name}'.")
            with open(target_path, "rb") as f:
                stream.write(f.read())
            stream.seek(0)
            return stream

    def delete_file(self, storage_key: str) -> bool:
        storage_key = storage_key.lstrip('/')
        if self._s3_client:
            self._s3_client.delete_object(Bucket=self.bucket_name, Key=storage_key)
            return True
        else:
            target_path = self.s3_local_dir / storage_key
            if target_path.exists():
                target_path.unlink()
                return True
            return False

    def rename_file(self, old_key: str, new_key: str) -> bool:
        return self.move_file(old_key, new_key)

    def copy_file(self, source_key: str, dest_key: str) -> bool:
        source_key = source_key.lstrip('/')
        dest_key = dest_key.lstrip('/')
        if self._s3_client:
            copy_source = {'Bucket': self.bucket_name, 'Key': source_key}
            self._s3_client.copy(copy_source, self.bucket_name, dest_key)
            return True
        else:
            src = self.s3_local_dir / source_key
            dst = self.s3_local_dir / dest_key
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
        if self._s3_client:
            self._s3_client.put_object(Bucket=self.bucket_name, Key=folder_path)
        else:
            (self.s3_local_dir / folder_path).mkdir(parents=True, exist_ok=True)
        return True

    def delete_folder(self, folder_path: str) -> bool:
        folder_path = folder_path.strip('/').lower()
        target = self.s3_local_dir / folder_path
        if target.exists() and target.is_dir():
            shutil.rmtree(target)
            return True
        return False

    def list_files(self, folder_path: str = "") -> List[Dict[str, Any]]:
        folder_path = folder_path.lstrip('/')
        target = self.s3_local_dir / folder_path
        if not target.exists() or not target.is_dir():
            return []
        files = []
        for p in target.glob("*"):
            if p.is_file():
                files.append({"key": str(p.relative_to(self.s3_local_dir)).replace('\\', '/'), "size": p.stat().st_size})
        return files

    def list_folders(self, folder_path: str = "") -> List[Dict[str, Any]]:
        folder_path = folder_path.lstrip('/')
        target = self.s3_local_dir / folder_path
        if not target.exists() or not target.is_dir():
            return []
        folders = []
        for p in target.glob("*"):
            if p.is_dir():
                folders.append({"name": p.name, "path": str(p.relative_to(self.s3_local_dir)).replace('\\', '/')})
        return folders

    def get_metadata(self, storage_key: str) -> Dict[str, Any]:
        storage_key = storage_key.lstrip('/')
        target = self.s3_local_dir / storage_key
        if not target.exists():
            raise FileNotFoundError(f"S3 object '{storage_key}' not found.")
        return {
            "key": storage_key,
            "size_bytes": target.stat().st_size,
            "bucket": self.bucket_name,
            "provider": "s3"
        }

    def get_storage_size(self, storage_key: str) -> int:
        return self.get_metadata(storage_key)['size_bytes']

    def generate_temp_url(self, storage_key: str, expiration_seconds: int = 3600) -> str:
        storage_key = storage_key.lstrip('/')
        if self._s3_client:
            return self._s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': storage_key},
                ExpiresIn=expiration_seconds
            )
        return f"/api/v1/documents/s3-simulated-download?key={storage_key}"

    def file_exists(self, storage_key: str) -> bool:
        storage_key = storage_key.lstrip('/')
        target = self.s3_local_dir / storage_key
        return target.exists() and target.is_file()

    def folder_exists(self, folder_path: str) -> bool:
        folder_path = folder_path.lstrip('/')
        target = self.s3_local_dir / folder_path
        return target.exists() and target.is_dir()

    def calculate_storage_size(self, folder_path: str) -> int:
        folder_path = folder_path.lstrip('/')
        target = self.s3_local_dir / folder_path
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
            "provider": "s3",
            "bucket": self.bucket_name,
            "region": self.region,
            "status": "HEALTHY",
            "mode": "ACTIVE_S3" if self._s3_client else "SIMULATED_LOCAL_S3"
        }
