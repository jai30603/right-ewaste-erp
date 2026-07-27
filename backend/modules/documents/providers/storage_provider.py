from abc import ABC, abstractmethod
from typing import BinaryIO, Dict, Any, List, Optional

class StorageProvider(ABC):
    """Abstract Base Class for all EDMS storage backends (Local, S3, Azure, GCP)."""

    @abstractmethod
    def upload_file(self, file_stream: BinaryIO, storage_key: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Uploads a file binary stream to storage and returns the storage_key."""
        pass

    @abstractmethod
    def download_file(self, storage_key: str) -> BinaryIO:
        """Retrieves binary stream for a stored file."""
        pass

    @abstractmethod
    def delete_file(self, storage_key: str) -> bool:
        """Deletes a physical file from storage."""
        pass

    @abstractmethod
    def rename_file(self, old_key: str, new_key: str) -> bool:
        """Renames a stored file."""
        pass

    @abstractmethod
    def move_file(self, source_key: str, destination_key: str) -> bool:
        """Moves a file within storage."""
        pass

    @abstractmethod
    def copy_file(self, source_key: str, destination_key: str) -> str:
        """Copies a file within storage and returns the new storage_key."""
        pass

    @abstractmethod
    def create_folder(self, folder_path: str) -> bool:
        """Creates a storage folder/directory."""
        pass

    @abstractmethod
    def delete_folder(self, folder_path: str) -> bool:
        """Deletes a storage folder/directory."""
        pass

    @abstractmethod
    def file_exists(self, storage_key: str) -> bool:
        """Checks if a file exists in storage."""
        pass

    @abstractmethod
    def folder_exists(self, folder_path: str) -> bool:
        """Checks if a folder exists in storage."""
        pass

    @abstractmethod
    def list_files(self, folder_path: str) -> List[str]:
        """Lists files inside a folder."""
        pass

    @abstractmethod
    def list_folders(self, folder_path: str) -> List[str]:
        """Lists subfolders inside a folder."""
        pass

    @abstractmethod
    def get_metadata(self, storage_key: str) -> Dict[str, Any]:
        """Gets storage object metadata (size, last_modified)."""
        pass

    @abstractmethod
    def calculate_storage_size(self, folder_path: str) -> int:
        """Calculates total size in bytes for a folder."""
        pass
