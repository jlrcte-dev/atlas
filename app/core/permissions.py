from enum import StrEnum


class ActionType(StrEnum):
    READ_EMAILS = "read_emails"
    DRAFT_EMAIL = "draft_email"
    SEND_EMAIL = "send_email"
    READ_CALENDAR = "read_calendar"
    CREATE_EVENT = "create_event"
    READ_NEWS = "read_news"
    GENERATE_BRIEFING = "generate_briefing"
