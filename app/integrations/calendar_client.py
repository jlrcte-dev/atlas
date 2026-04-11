"""Google Calendar integration client.

Uses Google Calendar API v3 with OAuth 2.0.

Setup:
  1. Baixe o arquivo OAuth credentials do Google Cloud Console
     (APIs & Services > Credentials > OAuth 2.0 Client IDs > Desktop app)
  2. Salve em credentials/google_oauth_credentials.json
  3. Na primeira execução, o browser abrirá para autorização.
     O token será salvo em credentials/google_token.json automaticamente.

Variáveis de ambiente:
  GOOGLE_CREDENTIALS_PATH  — path para o arquivo de credenciais OAuth (padrão: credentials/google_oauth_credentials.json)
  GOOGLE_TOKEN_PATH        — path onde o token será salvo (padrão: credentials/google_token.json)
  GOOGLE_CALENDAR_ID       — ID do calendário (padrão: "primary")
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("integrations.calendar")

# Escopos necessários: leitura e escrita de eventos
SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
]


@dataclass
class CalendarEvent:
    id: str
    title: str
    start: str  # formato HH:MM (normalizado do ISO retornado pela API)
    end: str
    location: str | None = None
    attendees: list[str] = field(default_factory=list)


def _build_service():
    """Constrói o serviço autenticado do Google Calendar.

    Tenta carregar token salvo; se ausente ou expirado, dispara fluxo OAuth.
    Levanta RuntimeError se as credenciais não estiverem configuradas.
    """
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError(
            "Dependências Google ausentes. Execute: "
            "pip install google-api-python-client google-auth-oauthlib google-auth-httplib2"
        ) from exc

    credentials_path = Path(settings.google_credentials_path)
    token_path = Path(settings.google_token_path)

    creds = None

    # Carrega token existente
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    # Renova ou dispara fluxo OAuth se necessário
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not credentials_path.exists():
                raise RuntimeError(
                    f"Arquivo de credenciais OAuth não encontrado: {credentials_path}\n"
                    "Baixe em: Google Cloud Console > APIs & Services > Credentials"
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
            creds = flow.run_local_server(port=0)

        # Persiste token para próximas execuções
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json())
        logger.info("Token OAuth salvo em %s", token_path)

    return build("calendar", "v3", credentials=creds)


def _parse_event_datetime(dt_obj: dict) -> str:
    """Extrai HH:MM de um objeto dateTime ou date da API do Google."""
    if "dateTime" in dt_obj:
        # Ex: "2026-04-11T09:00:00-03:00"
        dt_str = dt_obj["dateTime"]
        dt = datetime.fromisoformat(dt_str)
        return dt.strftime("%H:%M")
    # Evento de dia inteiro: retorna meia-noite como convenção
    return "00:00"


class GoogleCalendarClient:
    """Adapter para Google Calendar API v3.

    Mantém o mesmo contrato de interface do stub anterior:
    todos os métodos retornam CalendarEvent dataclasses ou dicts simples.
    """

    def __init__(self) -> None:
        self._service = None  # lazy init para não bloquear startup

    def _get_service(self):
        if self._service is None:
            self._service = _build_service()
        return self._service

    def get_today_events(self) -> list[CalendarEvent]:
        """Retorna eventos do dia atual no calendário configurado."""
        try:
            now = datetime.now(tz=timezone.utc)
            start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=0)
            return self._fetch_events(
                time_min=start_of_day.isoformat(),
                time_max=end_of_day.isoformat(),
            )
        except Exception:
            logger.exception("get_today_events falhou — retornando lista vazia")
            return []

    def get_events_range(self, start_date: str, end_date: str) -> list[CalendarEvent]:
        """Retorna eventos entre duas datas (formato ISO 8601 ou YYYY-MM-DD)."""
        try:
            if "T" not in start_date:
                start_date = f"{start_date}T00:00:00Z"
            if "T" not in end_date:
                end_date = f"{end_date}T23:59:59Z"
            logger.info("get_events_range %s to %s", start_date, end_date)
            return self._fetch_events(time_min=start_date, time_max=end_date)
        except Exception:
            logger.exception("get_events_range falhou — retornando lista vazia")
            return []

    def _fetch_events(self, time_min: str, time_max: str) -> list[CalendarEvent]:
        """Executa a chamada à API e converte para CalendarEvent."""
        service = self._get_service()
        calendar_id = settings.google_calendar_id

        result = (
            service.events()
            .list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        items = result.get("items", [])
        events: list[CalendarEvent] = []

        for item in items:
            start = item.get("start", {})
            end = item.get("end", {})
            attendees_raw = item.get("attendees", [])
            attendees = [
                a.get("email", "") for a in attendees_raw if a.get("email")
            ]

            events.append(
                CalendarEvent(
                    id=item.get("id", ""),
                    title=item.get("summary", "(sem título)"),
                    start=_parse_event_datetime(start),
                    end=_parse_event_datetime(end),
                    location=item.get("location"),
                    attendees=attendees,
                )
            )

        logger.info("_fetch_events: %d evento(s) encontrado(s)", len(events))
        return events

    def create_event(
        self,
        title: str,
        start: str,
        end: str,
        location: str | None = None,
        attendees: list[str] | None = None,
    ) -> dict:
        """Cria evento no Google Calendar. Deve ser chamado APENAS após aprovação."""
        try:
            service = self._get_service()
            calendar_id = settings.google_calendar_id

            today = datetime.now().strftime("%Y-%m-%d")
            timezone_id = settings.timezone

            def _to_iso(time_str: str) -> str:
                if "T" in time_str:
                    return time_str
                return f"{today}T{time_str}:00"

            event_body: dict = {
                "summary": title,
                "start": {"dateTime": _to_iso(start), "timeZone": timezone_id},
                "end": {"dateTime": _to_iso(end), "timeZone": timezone_id},
            }

            if location:
                event_body["location"] = location
            if attendees:
                event_body["attendees"] = [{"email": email} for email in attendees]

            created = service.events().insert(calendarId=calendar_id, body=event_body).execute()
            event_id = created.get("id", "")
            logger.info("create_event: evento criado id=%s title=%s", event_id, title)
            return {"status": "created", "event_id": event_id}
        except Exception:
            logger.exception("create_event falhou title=%s", title)
            return {"status": "error", "event_id": ""}

    @staticmethod
    def to_dict(event: CalendarEvent) -> dict:
        return asdict(event)
