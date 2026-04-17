"""Microsoft OAuth2 authentication via MSAL (PublicClientApplication + PKCE).

Runtime helper used by the Outlook integration. Loads the persisted token cache
and returns a valid access token silently. Requires a prior interactive login
via `python scripts/auth_microsoft.py`.

Completely independent from the Google auth flow — separate cache file,
separate library (msal), separate config keys.
"""

from __future__ import annotations

from pathlib import Path

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("integrations.microsoft_auth")

MICROSOFT_SCOPES = ["Mail.Read"]


def _authority() -> str:
    return f"https://login.microsoftonline.com/{settings.microsoft_tenant}"


def _load_cache():
    """Load the MSAL SerializableTokenCache from disk (if present)."""
    from msal import SerializableTokenCache

    cache = SerializableTokenCache()
    cache_path = Path(settings.microsoft_token_cache_path)
    if cache_path.exists():
        try:
            cache.deserialize(cache_path.read_text())
            logger.debug("Token cache carregado de %s", cache_path)
        except Exception as exc:
            logger.warning("Falha ao carregar cache MSAL (%s) — ignorando", exc)
    return cache


def _save_cache(cache) -> None:
    if not cache.has_state_changed:
        return
    cache_path = Path(settings.microsoft_token_cache_path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(cache.serialize())
    logger.debug("Token cache persistido em %s", cache_path)


def build_public_app(cache=None):
    """Create a PublicClientApplication (no client_secret — PKCE flow)."""
    try:
        from msal import PublicClientApplication
    except ImportError as exc:
        raise RuntimeError(
            "MSAL ausente. Execute: pip install msal>=1.30.0"
        ) from exc

    if not settings.microsoft_client_id:
        raise RuntimeError(
            "MICROSOFT_CLIENT_ID nao configurado. "
            "Registre um app em portal.azure.com e defina no .env."
        )

    return PublicClientApplication(
        client_id=settings.microsoft_client_id,
        authority=_authority(),
        token_cache=cache,
    )


def get_microsoft_access_token(scopes: list[str] | None = None) -> str:
    """Return a valid Microsoft Graph access token for the cached account.

    Flow:
      1. Load serialized cache from disk
      2. Build PublicClientApplication bound to that cache
      3. Pick the first cached account
      4. acquire_token_silent (auto-refresh if needed)
      5. Persist cache if it changed
      6. Return access_token string

    Raises:
        RuntimeError: if no cached account or silent acquisition fails
                      (user must run scripts/auth_microsoft.py first).
    """
    target_scopes = scopes or MICROSOFT_SCOPES
    cache = _load_cache()
    app = build_public_app(cache=cache)

    accounts = app.get_accounts()
    if not accounts:
        raise RuntimeError(
            f"Nenhuma conta Microsoft em cache ({settings.microsoft_token_cache_path}).\n"
            "Execute: python scripts/auth_microsoft.py"
        )

    result = app.acquire_token_silent(scopes=target_scopes, account=accounts[0])
    _save_cache(cache)

    if not result or "access_token" not in result:
        raise RuntimeError(
            "Token Microsoft expirado ou invalido. "
            "Execute novamente: python scripts/auth_microsoft.py"
        )

    return result["access_token"]
