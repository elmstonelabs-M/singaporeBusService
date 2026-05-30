class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class ExternalServiceError(AppError):
    def __init__(
        self,
        code: str,
        message: str = "External service error.",
        status_code: int = 503,
    ) -> None:
        super().__init__(code=code, message=message, status_code=status_code)
