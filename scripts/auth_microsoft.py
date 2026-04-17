"""Atlas AI Assistant — Microsoft OAuth authorization tool.

Run ONCE to populate credentials/microsoft_token_cache.json before using the
Outlook integration. Uses MSAL PublicClientApplication with PKCE — no
client_secret required.

Usage:
    python scripts/auth_microsoft.py

Requirements:
    - MICROSOFT_CLIENT_ID set in .env (Azure AD app, "Mobile and desktop applications")
    - Delegated permission: Mail.Read
    - Browser access (interactive flow opens a local login window)
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.integrations.microsoft_auth import (
    MICROSOFT_SCOPES,
    _load_cache,
    _save_cache,
    build_public_app,
)

configure_logging()
logger = get_logger("scripts.auth_microsoft")


def main() -> int:
    print("\n=== Atlas AI Assistant — Autorizacao Microsoft OAuth ===\n")

    if not settings.microsoft_client_id:
        print("ERRO: MICROSOFT_CLIENT_ID nao configurado no .env.")
        print("  1) Registre um app em: https://portal.azure.com")
        print("     Azure AD > App registrations > New registration")
        print("  2) Tipo: Mobile and desktop applications (public client)")
        print("  3) Adicione a permissao delegada: Mail.Read")
        print("  4) Copie o Application (client) ID para MICROSOFT_CLIENT_ID no .env")
        return 1

    cache_path = Path(settings.microsoft_token_cache_path)
    print(f"Client ID : {settings.microsoft_client_id}")
    print(f"Tenant    : {settings.microsoft_tenant}")
    print(f"Cache     : {cache_path.resolve()}")
    print(f"Scopes    : {MICROSOFT_SCOPES}\n")

    try:
        cache = _load_cache()
        app = build_public_app(cache=cache)
    except RuntimeError as exc:
        print(f"ERRO: {exc}")
        return 1

    print("Iniciando fluxo interativo — uma janela de login do Microsoft vai abrir.")
    print("Faca login e conceda a permissao Mail.Read.\n")

    try:
        result = app.acquire_token_interactive(scopes=MICROSOFT_SCOPES)
    except Exception as exc:
        print(f"\nERRO durante o fluxo OAuth: {type(exc).__name__}: {exc}")
        logger.exception("Falha no fluxo OAuth Microsoft")
        return 1

    if "access_token" not in result:
        err = result.get("error_description") or result.get("error") or "desconhecido"
        print(f"\nERRO: token nao obtido. Detalhe: {err}")
        return 1

    try:
        _save_cache(cache)
    except Exception as exc:
        print(f"\nERRO ao persistir cache: {exc}")
        logger.exception("Falha ao salvar cache MSAL")
        return 1

    account = result.get("id_token_claims", {}).get("preferred_username", "(desconhecido)")
    print(f"\nSucesso! Conta autorizada: {account}")
    print(f"Cache salvo em: {cache_path.resolve()}")
    print("\nAgora voce pode definir EMAIL_PROVIDER=outlook no .env quando o OutlookClient estiver pronto.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
