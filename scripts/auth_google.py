"""Atlas AI Assistant — Google OAuth authorization tool.

Run ONCE to generate credentials/google_token.json before starting the API.
Requests all scopes needed by Calendar and Drive integrations.

Usage:
    python scripts/auth_google.py

Requirements:
    - credentials/google_oauth_credentials.json must exist (Desktop App type)
    - Browser access (will open automatically)
"""

from __future__ import annotations

import ssl
import sys
from pathlib import Path

# ── Add project root to sys.path ──────────────────────────────────
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from app.core.config import settings
from app.core.logging import configure_logging, get_logger

configure_logging()
logger = get_logger("scripts.auth_google")

# All scopes required across Calendar and Drive integrations.
# Requesting them together avoids repeated OAuth prompts per service.
ALL_SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
]


def _patch_system_certs() -> None:
    """Inject Windows system certificates into ssl for MITM proxy/AV compatibility.

    When an antivirus or corporate proxy intercepts HTTPS (MITM), it replaces
    Google's certificate with its own. The `requests` library uses `certifi`
    (a bundled CA store) which doesn't know the AV/proxy CA, causing SSLError.

    Two layers of protection:
    1. pip-system-certs (.pth file) — active at interpreter startup automatically.
    2. truststore (if installed) — explicit injection via ssl module for belt-and-
       suspenders. Safe to skip if not installed.
    """
    try:
        import truststore  # type: ignore[import-not-found]

        truststore.inject_into_ssl()
        logger.debug("truststore: certificados do sistema Windows injetados no ssl")
    except ImportError:
        pass  # rely on pip-system-certs .pth injection (enough in most cases)


def _patch_ssl_eof() -> None:
    """Patch ssl.create_default_context to suppress UNEXPECTED_EOF_WHILE_READING.

    Python 3.12+ / OpenSSL 3.0 raises this error when a TLS 1.3 connection
    closes without a proper close_notify alert. This is common on Windows with
    TLS inspection tools (antivirus, Windows Defender) intercepting the
    connection to oauth2.googleapis.com.

    OP_IGNORE_UNEXPECTED_EOF was added in Python 3.12 specifically for this.
    """
    if not hasattr(ssl, "OP_IGNORE_UNEXPECTED_EOF"):
        return  # Python < 3.12 — not needed

    _orig = ssl.create_default_context

    def _patched(*args: object, **kwargs: object) -> ssl.SSLContext:
        ctx = _orig(*args, **kwargs)
        ctx.options |= ssl.OP_IGNORE_UNEXPECTED_EOF
        return ctx

    ssl.create_default_context = _patched
    logger.debug("SSL EOF patch aplicado (OP_IGNORE_UNEXPECTED_EOF)")


def _verify_connectivity() -> bool:
    """Quick check that oauth2.googleapis.com is reachable before starting OAuth."""
    try:
        import urllib.request
        urllib.request.urlopen("https://oauth2.googleapis.com/tokeninfo", timeout=5)
    except Exception as exc:
        # 400/404 from Google is fine — means we reached the server
        err_str = str(exc)
        if "400" in err_str or "404" in err_str or "HTTP Error" in err_str:
            return True
        logger.error("Falha de conectividade com oauth2.googleapis.com: %s", exc)
        return False
    return True


def main() -> int:
    credentials_path = Path(settings.google_credentials_path)
    token_path = Path(settings.google_token_path)

    print("\n=== Atlas AI Assistant — Autorização Google OAuth ===\n")

    # Pre-flight checks
    if not credentials_path.exists():
        print(f"ERRO: arquivo de credenciais não encontrado: {credentials_path}")
        print("  Baixe em: Google Cloud Console > APIs & Services > Credentials")
        print("  Tipo necessário: Desktop app (OAuth 2.0 Client ID)")
        return 1

    print(f"Credenciais: {credentials_path}")
    print(f"Token destino: {token_path.resolve()}")
    print(f"Scopes: {len(ALL_SCOPES)} (Calendar + Drive)\n")

    # Layer 1: inject Windows system certs (handles antivirus/proxy MITM)
    _patch_system_certs()
    # Layer 2: tolerate TLS close_notify absence (Python 3.12 + OpenSSL 3.0)
    _patch_ssl_eof()

    # Connectivity check
    print("Verificando conectividade com Google...")
    if not _verify_connectivity():
        print("AVISO: possível problema de rede ou proxy. Continuando mesmo assim...")
    else:
        print("Conectividade OK.\n")

    # Load Google auth libraries
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("ERRO: dependências Google ausentes.")
        print("Execute: pip install google-auth-oauthlib google-api-python-client")
        return 1

    # Create and run OAuth flow
    print("Iniciando fluxo OAuth — o browser vai abrir automaticamente.")
    print("Faça login com sua conta Google e conceda as permissões solicitadas.\n")

    try:
        flow = InstalledAppFlow.from_client_secrets_file(
            str(credentials_path), ALL_SCOPES
        )
        creds = flow.run_local_server(port=0)
    except Exception as exc:
        print(f"\nERRO durante o fluxo OAuth: {type(exc).__name__}: {exc}")
        logger.exception("Falha no fluxo OAuth")
        return 1

    # Save token
    try:
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json())
    except Exception as exc:
        print(f"\nERRO ao salvar token: {exc}")
        logger.exception("Falha ao salvar token")
        return 1

    print(f"\nSucesso! Token salvo em: {token_path.resolve()}")
    print(f"Scopes autorizados: {len(creds.scopes or [])}")
    print("\nAgora você pode iniciar a API:")
    print("  uvicorn app.main:app --port 8000\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
