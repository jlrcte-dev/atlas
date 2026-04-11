class GoogleWorkspaceMCPClient:
    def list_recent_emails(self) -> list[dict]:
        return [
            {"from": "cliente@empresa.com", "subject": "Reunião pendente", "priority": "alta"},
            {"from": "newsletter@mercado.com", "subject": "Resumo macro", "priority": "media"},
        ]

    def get_today_events(self) -> list[dict]:
        return [
            {"time": "09:00", "title": "Call com equipe", "location": "Google Meet"},
            {"time": "15:00", "title": "Revisão semanal", "location": "Escritório"},
        ]
