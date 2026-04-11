"""Google Drive integration client.

Uses Google Drive API v3 with OAuth 2.0 via shared google_auth module.

Setup:
  Same credentials file as Calendar (credentials/google_oauth_credentials.json).
  On first Drive call, browser may open to authorize additional Drive scope.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from app.core.logging import get_logger
from app.integrations.google_auth import get_google_credentials

logger = get_logger("integrations.drive")

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

# Fields requested from the API — explicit to avoid large payloads
_FILE_FIELDS = "id,name,mimeType,modifiedTime,size,parents,webViewLink"
_LIST_FIELDS = f"files({_FILE_FIELDS}),nextPageToken"

# Max files per request — reasonable for Fase 1
_PAGE_SIZE = 50


@dataclass
class DriveFile:
    id: str
    name: str
    mime_type: str
    modified_time: str
    size: int | None  # None for Google Docs native formats (no byte size)
    web_view_link: str
    parents: list[str]


def _build_service():
    """Build authenticated Google Drive service using shared auth."""
    from googleapiclient.discovery import build

    creds = get_google_credentials(SCOPES)
    return build("drive", "v3", credentials=creds)


def _parse_file(item: dict) -> DriveFile:
    """Convert a Drive API file resource to DriveFile dataclass."""
    size_str = item.get("size")
    return DriveFile(
        id=item.get("id", ""),
        name=item.get("name", "(sem nome)"),
        mime_type=item.get("mimeType", ""),
        modified_time=item.get("modifiedTime", ""),
        size=int(size_str) if size_str else None,
        web_view_link=item.get("webViewLink", ""),
        parents=item.get("parents", []),
    )


class GoogleDriveClient:
    """Adapter for Google Drive API v3."""

    def __init__(self) -> None:
        self._service = None  # lazy init

    def _get_service(self):
        if self._service is None:
            self._service = _build_service()
        return self._service

    def list_files(self, folder_id: str | None = None) -> list[DriveFile]:
        """List files in a folder (or root if folder_id is None).

        Returns up to 50 files ordered by modified time (most recent first).
        Folders themselves are excluded — only files are returned.
        """
        try:
            query_parts = ["trashed = false", "mimeType != 'application/vnd.google-apps.folder'"]
            if folder_id:
                query_parts.append(f"'{folder_id}' in parents")

            return self._fetch_files(query=" and ".join(query_parts))
        except Exception:
            logger.exception("list_files failed (folder_id=%s)", folder_id)
            return []

    def search_files(self, query: str) -> list[DriveFile]:
        """Search files by name across the entire Drive.

        Args:
            query: Search term (matched against file names).

        Returns up to 50 matching files ordered by modified time.
        """
        try:
            if not query or not query.strip():
                return []
            safe_query = query.replace("'", "\\'")
            full_query = (
                f"name contains '{safe_query}' and trashed = false "
                "and mimeType != 'application/vnd.google-apps.folder'"
            )
            return self._fetch_files(query=full_query)
        except Exception:
            logger.exception("search_files failed (query=%r)", query)
            return []

    def get_file_metadata(self, file_id: str) -> DriveFile | None:
        """Return metadata for a single file by ID."""
        try:
            service = self._get_service()
            item = (
                service.files()
                .get(fileId=file_id, fields=_FILE_FIELDS)
                .execute()
            )
            return _parse_file(item)
        except Exception:
            logger.exception("get_file_metadata failed (file_id=%s)", file_id)
            return None

    def _fetch_files(self, query: str) -> list[DriveFile]:
        """Execute Drive files.list API call and convert to DriveFile list."""
        service = self._get_service()

        result = (
            service.files()
            .list(
                q=query,
                pageSize=_PAGE_SIZE,
                fields=_LIST_FIELDS,
                orderBy="modifiedTime desc",
            )
            .execute()
        )

        items = result.get("files", [])
        files = [_parse_file(item) for item in items]

        logger.info("_fetch_files: %d file(s) found (query=%r)", len(files), query)
        return files

    @staticmethod
    def to_dict(file: DriveFile) -> dict:
        return asdict(file)
