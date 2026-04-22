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


# ── Finance ───────────────────────────────────────────────────────


class FinanceError(AtlasError):
    """Base exception for Finance module errors."""


class FinanceNotFoundError(FinanceError):
    def __init__(self, resource: str, resource_id: int) -> None:
        super().__init__(
            f"{resource} #{resource_id} não encontrado.",
            code="FINANCE_NOT_FOUND",
        )


class FinanceInvalidMonthRefError(FinanceError):
    def __init__(self, month_ref: str) -> None:
        super().__init__(
            f"Formato de month_ref inválido: '{month_ref}'. Use YYYY-MM.",
            code="FINANCE_INVALID_MONTH_REF",
        )


class FinanceMissingClosingError(FinanceError):
    def __init__(self, month_ref: str) -> None:
        super().__init__(
            f"Nenhum fechamento mensal encontrado para {month_ref}. "
            "Registre o saldo inicial antes de consultar o resumo.",
            code="FINANCE_MISSING_CLOSING",
        )


class FinanceDuplicateClosingError(FinanceError):
    def __init__(self, month_ref: str) -> None:
        super().__init__(
            f"Já existe um fechamento mensal para {month_ref}.",
            code="FINANCE_DUPLICATE_CLOSING",
        )


class FinanceDuplicateSnapshotError(FinanceError):
    def __init__(self, account_id: int, month_ref: str) -> None:
        super().__init__(
            f"Já existe um snapshot para a conta #{account_id} em {month_ref}.",
            code="FINANCE_DUPLICATE_SNAPSHOT",
        )
