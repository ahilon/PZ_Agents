"""File operation tools"""
import asyncio
import logging
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


class FileTools:
    """Tools for file operations"""

    @staticmethod
    async def read_file(file_path: str) -> Optional[str]:
        """Read file content"""
        try:
            return await asyncio.to_thread(Path(file_path).read_text, encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {str(e)}")
            return None

    @staticmethod
    async def write_file(file_path: str, content: str) -> bool:
        """Write content to file"""
        def _write():
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

        try:
            await asyncio.to_thread(_write)
            logger.info(f"File written: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to write file {file_path}: {str(e)}")
            return False

    @staticmethod
    async def list_files(directory: str, pattern: str = "*") -> List[str]:
        """List files in directory"""
        def _list():
            return [str(f) for f in Path(directory).glob(pattern) if f.is_file()]

        try:
            return await asyncio.to_thread(_list)
        except Exception as e:
            logger.error(f"Failed to list files in {directory}: {str(e)}")
            return []

    @staticmethod
    async def delete_file(file_path: str) -> bool:
        """Delete a file"""
        try:
            await asyncio.to_thread(Path(file_path).unlink)
            logger.info(f"File deleted: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete file {file_path}: {str(e)}")
            return False
