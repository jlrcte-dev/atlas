from dataclasses import dataclass


@dataclass(frozen=True)
class SecurityPolicy:
    default_mode: str = "read_only"
    require_approval_for_email_send: bool = True
    require_approval_for_event_create: bool = True


security_policy = SecurityPolicy()
