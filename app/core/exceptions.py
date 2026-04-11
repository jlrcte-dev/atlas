"""Custom exceptions for Atlas AI Assistant."""


class AtlasError(Exception):
    """Base exception for all Atlas-specific errors."""

    def __init__(self, message: str, code: str = "INTERNAL_ERROR") -> None:
        self.message = message
        self.code = code
        super().__init__(message)


class ActionNotFoundError(AtlasError):
    def __init__(self, action_id: int) -> None:
        super().__init__(
            f"Acao #{action_id} nao encontrada.",
            code="ACTION_NOT_FOUND",
        )


class ActionAlreadyResolvedError(AtlasError):
    def __init__(self, action_id: int, current_status: str) -> None:
        super().__init__(
            f"Acao #{action_id} ja foi processada (status: {current_status}).",
            code="ACTION_ALREADY_RESOLVED",
        )


class UnauthorizedError(AtlasError):
    def __init__(self, message: str = "Acesso nao autorizado.") -> None:
        super().__init__(message, code="UNAUTHORIZED")


class IntegrationError(AtlasError):
    def __init__(self, service: str, detail: str = "") -> None:
        msg = f"Erro na integracao [{service}]"
        if detail:
            msg += f": {detail}"
        super().__init__(msg, code="INTEGRATION_ERROR")
