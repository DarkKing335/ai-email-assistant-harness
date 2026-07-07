import os
from pathlib import Path
from typing import Protocol, BinaryIO

class StorageClient(Protocol):
    async def upload(self, object_name: str, file_obj: BinaryIO) -> str:
        ...
        
    async def download(self, object_name: str) -> bytes:
        ...
        
    async def delete(self, object_name: str) -> None:
        ...

class LocalFileStore:
    """
    A local file system storage client for attachments and temporary files.
    """
    def __init__(self, base_dir: str = "./data/storage"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
    async def upload(self, object_name: str, file_obj: BinaryIO) -> str:
        file_path = self.base_dir / object_name
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, "wb") as f:
            f.write(file_obj.read())
            
        return str(file_path)
        
    async def download(self, object_name: str) -> bytes:
        file_path = self.base_dir / object_name
        if not file_path.exists():
            raise FileNotFoundError(f"Object {object_name} not found")
            
        with open(file_path, "rb") as f:
            return f.read()
            
    async def delete(self, object_name: str) -> None:
        file_path = self.base_dir / object_name
        if file_path.exists():
            os.remove(file_path)

storage_client: StorageClient = LocalFileStore()
