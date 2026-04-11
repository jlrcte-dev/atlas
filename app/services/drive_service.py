"""Drive Copilot service.

Lists and searches files in Google Drive.
"""

from __future__ import annotations

from app.core.config import settings
from app.core.logging import get_logger, log_action
from app.integrations.drive_client import GoogleDriveClient

logger = get_logger("services.drive")


class DriveService:
    def __init__(self) -> None:
        self.client = GoogleDriveClient()

    def list_files(self) -> dict:
        """Return files from the configured root folder (or all Drive if unset)."""
        folder_id = settings.google_drive_root_folder or None
        files = self.client.list_files(folder_id=folder_id)
        items = [GoogleDriveClient.to_dict(f) for f in files]
        result = {
            "total": len(files),
            "files": items,
            "summary": f"{len(files)} arquivo(s) encontrado(s).",
        }
        log_action(logger, "list_files", total=len(files), folder_id=folder_id)
        return result

    def search_files(self, query: str) -> dict:
        """Search files by name across Drive."""
        files = self.client.search_files(query)
        items = [GoogleDriveClient.to_dict(f) for f in files]
        result = {
            "total": len(files),
            "files": items,
            "query": query,
            "summary": f"{len(files)} arquivo(s) encontrado(s) para '{query}'.",
        }
        log_action(logger, "search_files", query=query, total=len(files))
        return result
