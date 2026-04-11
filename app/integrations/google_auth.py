"""Shared Google OAuth2 authentication.

Provides a single function to obtain valid Google credentials,
reusable by Calendar, Drive, and Gmail clients.

The first call with new scopes triggers browser-based OAuth consent.
Subsequent calls reuse the saved token (with automatic refresh).
"""

from __future__ import annotations

from pathlib import Path

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("integrations.google_auth")


def get_google_credentials(scopes: list[str]):
    """Return valid Google OAuth2 Credentials for the given scopes.

    Flow:
      1. Load saved token from GOOGLE_TOKEN_PATH (if exists)
      2. If valid, return immediately
      3. If expired with refresh_token, refresh automatically
      4. Otherwise, launch browser-based OAuth consent flow
      5. Save the resulting token for next time

    Raises RuntimeError if google libs are missing or credentials file not found.
    """
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:
        raise RuntimeError(
            "Google auth dependencies missing. Run: "
            "pip install google-api-python-client google-auth-oauthlib google-auth-httplib2"
        ) from exc

    credentials_path = Path(settings.google_credentials_path)
    token_path = Path(settings.google_token_path)

    creds = None

    # 1. Load existing token
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), scopes)
        logger.debug("Token loaded from %s", token_path)

        # If token doesn't cover requested scopes (e.g. new integration added),
        # discard and re-auth — avoids silent 403s on API calls
        if creds and creds.scopes and not set(scopes).issubset(creds.scopes):
            logger.info("Token missing required scopes %s — re-authenticating", scopes)
            creds = None

    # 2. Refresh or run OAuth flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.info("Token expired, refreshing...")
            creds.refresh(Request())
        else:
            if not credentials_path.exists():
                raise RuntimeError(
                    f"OAuth credentials file not found: {credentials_path}\n"
                    "Download from: Google Cloud Console > APIs & Services > Credentials"
                )
            logger.info("No valid token — launching OAuth consent flow")
            flow = InstalledAppFlow.from_client_secrets_file(
                str(credentials_path), scopes
            )
            creds = flow.run_local_server(port=0)

        # 3. Persist token
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json())
        logger.info("Token saved to %s", token_path)

    return creds
