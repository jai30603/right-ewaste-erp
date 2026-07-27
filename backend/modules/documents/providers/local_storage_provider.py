import os
import shutil
import hashlib
from io import BytesIO
from pathlib import Path
from typing import BinaryIO, Dict, Any, List, Optional
from backend.modules.documents.providers.storage_provider import StorageProvider

class LocalStorageProvider(StorageProvider):
    """Concrete implementation of StorageProvider using the local filesystem."""

    def __init__(self, base_dir: Optional[str] = None):
        if base_dir:
            self.base_path = Path(base_dir).resolve()
        else:
            self.base_path = Path(__file__).resolve().parent.parent.parent.parent.parent / "storage"
        
        # Ensure root storage directories exist
        for category in ["company", "users", "modules", "system", "temp", "trash"]:
            (self.base_path / category).mkdir(parents=True, exist_ok=True)

    def _resolve_path(self, storage_key: str) -> Path:
        """Resolves relative storage key to absolute safe path."""
        clean_key = storage_key.lstrip("/\\")
        resolved = (self.base_path / clean_key).resolve()
        # Security check: Prevent directory traversal escape
        if not str(resolved).startswith(str(self.base_path)):
            raise ValueError(f"Security Error: Invalid storage path traversal '{storage_key}'")
        return resolved

    def upload_file(self, file_stream: BinaryIO, storage_key: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        target_path = self._resolve_path(storage_key)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(target_path, "wb") as dest:
            shutil.copyfileobj(file_stream, dest)
            
        return storage_key

    def download_file(self, storage_key: str) -> BinaryIO:
        target_path = self._resolve_path(storage_key)
        if not target_path.exists() or not target_path.is_file():
            raise FileNotFoundError(f"File not found in local storage: {storage_key}")
        
        with open(target_path, "rb") as f:
            data = f.read()
        return BytesIO(data)

    def delete_file(self, storage_key: str) -> bool:
        target_path = self._resolve_path(storage_key)
        if target_path.exists() and target_path.is_file():
            target_path.unlink()
            return True
        return False

    def rename_file(self, old_key: str, new_key: str) -> bool:
        return self.move_file(old_key, new_key)

    def move_file(self, source_key: str, destination_key: str) -> bool:
        src_path = self._resolve_path(source_key)
        dest_path = self._resolve_path(destination_key)
        if not src_path.exists():
            raise FileNotFoundError(f"Source file not found: {source_key}")
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(src_path, dest_path)
        return True

    def copy_file(self, source_key: str, destination_key: str) -> str:
        src_path = self._resolve_path(source_key)
        dest_path = self._resolve_path(destination_key)
        if not src_path.exists():
            raise FileNotFoundError(f"Source file not found: {source_key}")
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_path, dest_path)
        return destination_key

    def create_folder(self, folder_path: str) -> bool:
        target_path = self._resolve_path(folder_path)
        target_path.mkdir(parents=True, exist_ok=True)
        return True

    def delete_folder(self, folder_path: str) -> bool:
        target_path = self._resolve_path(folder_path)
        if target_path.exists() and target_path.is_dir():
            shutil.rmtree(target_path)
            return True
        return False

    def file_exists(self, storage_key: str) -> bool:
        target_path = self._resolve_path(storage_key)
        return target_path.exists() and target_path.is_file()

    def folder_exists(self, folder_path: str) -> bool:
        target_path = self._resolve_path(folder_path)
        return target_path.exists() and target_path.is_dir()

    def list_files(self, folder_path: str) -> List[str]:
        target_path = self._resolve_path(folder_path)
        if not target_path.exists() or not target_path.is_dir():
            return []
        return [f.name for f in target_path.iterdir() if f.is_file()]

    def list_folders(self, folder_path: str) -> List[str]:
        target_path = self._resolve_path(folder_path)
        if not target_path.exists() or not target_path.is_dir():
            return []
        return [f.name for f in target_path.iterdir() if f.is_dir()]

    def get_metadata(self, storage_key: str) -> Dict[str, Any]:
        target_path = self._resolve_path(storage_key)
        if not target_path.exists():
            raise FileNotFoundError(f"File not found: {storage_key}")
        stat = target_path.stat()
        return {
            "size_bytes": stat.st_size,
            "created_at": stat.st_ctime,
            "modified_at": stat.st_mtime,
            "is_file": target_path.is_file()
        }

    def calculate_storage_size(self, folder_path: str) -> int:
        target_path = self._resolve_path(folder_path)
        if not target_path.exists():
            return 0
        total = 0
        if target_path.is_file():
            return target_path.stat().st_size
        for path in target_path.rglob("*"):
            if path.is_file():
                total += path.stat().st_size
        return total

    def health_check(self) -> Dict[str, Any]:
        return {
            "provider": "local",
            "base_path": str(self.base_path),
            "status": "HEALTHY"
        }

    @staticmethod
    def calculate_sha256(file_stream: BinaryIO) -> str:
        """Calculates SHA-256 hash of a file stream."""
        hasher = hashlib.sha256()
        file_stream.seek(0)
        while chunk := file_stream.read(8192):
            hasher.update(chunk)
        file_stream.seek(0)
        return hasher.hexdigest()
