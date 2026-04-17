"""Shared Google OAuth2 authentication.

Provides a single function to obtain valid Google credentials,
reusable by Calendar, Drive, and Gmail clients.

First-time setup: run `python scripts/auth_google.py` to generate the token.
Subsequent calls reuse and auto-refresh the saved token.
"""

from __future__ import annotations

import ssl
from pathlib import Path

from app.core.config import settings
from app.core.logging import get_logger

GOOGLE_ALL_SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
]

logger = get_logger("integrations.google_auth")


def _apply_ssl_eof_fix() -> None:
    """Patch ssl.create_default_context to suppress UNEXPECTED_EOF_WHILE_READING.

    Python 3.12+ / OpenSSL 3.0 raises this error when TLS connections close
    without a proper close_notify alert — common on Windows with TLS inspection.
    OP_IGNORE_UNEXPECTED_EOF (added in Python 3.12) restores the pre-3.0 behavior.

    This patch is applied once at module import and is intentionally persistent
    so it also covers token refresh calls made by google-auth.
    """
    if not hasattr(ssl, "OP_IGNORE_UNEXPECTED_EOF"):
        return

    _orig = ssl.create_default_context

    def _patched(*args: object, **kwargs: object) -> ssl.SSLContext:
        ctx = _orig(*args, **kwargs)
        ctx.options |= ssl.OP_IGNORE_UNEXPECTED_EOF
        return ctx

    ssl.create_default_context = _patched
    logger.debug("SSL OP_IGNORE_UNEXPECTED_EOF patch aplicado")


# Apply once when the module is first imported.
# Covers both the initial OAuth flow and all subsequent token refreshes.
_apply_ssl_eof_fix()


def get_google_credentials(scopes: list[str]):
    """Return valid Google OAuth2 Credentials for the given scopes.

    Flow:
      1. Load saved token from GOOGLE_TOKEN_PATH (if exists)
      2. If valid, return immediately
      3. If expired with refresh_token, refresh automatically
      4. Otherwise, raise RuntimeError — run scripts/auth_google.py first

    Raises:
        RuntimeError: if credentials file is missing or no valid token exists.
    """
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
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
        try:
            creds = Credentials.from_authorized_user_file(str(token_path), GOOGLE_ALL_SCOPES)
            logger.debug("Token carregado de %s | valid=%s", token_path, creds.valid)
        except Exception as exc:
            logger.warning("Falha ao carregar token existente (%s) — ignorando", exc)
            creds = None

        # If saved token doesn't cover the requested scopes, discard and re-auth
        if creds and creds.scopes and not set(scopes).issubset(set(creds.scopes)):
            logger.info("Token sem scopes necessários %s — re-autenticação necessária", scopes)
            creds = None

    # 2. Refresh expired token
    if creds and creds.expired and creds.refresh_token:
        logger.info("Token expirado — refreshing...")
        try:
            creds.refresh(Request())
            logger.info("Token refreshed OK")
            token_path.write_text(creds.to_json())
        except Exception as exc:
            logger.error("Falha no refresh do token: %s", exc, exc_info=True)
            creds = None

    # 3. No valid token — direct the user to run the auth script
    if not creds or not creds.valid:
        if not credentials_path.exists():
            raise RuntimeError(
                f"OAuth credentials file not found: {credentials_path}\n"
                "Download from: Google Cloud Console > APIs & Services > Credentials"
            )
        raise RuntimeError(
            f"No valid Google token found at {token_path}.\n"
            "Run: python scripts/auth_google.py"
        )

    return creds
