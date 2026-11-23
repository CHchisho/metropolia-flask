"""Domain errors. The API layer maps them to JSON responses."""


class AppError(Exception):
    status_code = 500
    code = "internal_error"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class ValidationError(AppError):
    status_code = 400
    code = "validation_error"


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class PayloadTooLargeError(AppError):
    status_code = 413
    code = "payload_too_large"


class ProcessingError(AppError):
    """A document could not be read or indexed."""

    status_code = 422
    code = "processing_error"


class ProviderError(AppError):
    """The upstream LLM / embedding provider failed."""

    status_code = 502
    code = "provider_error"
