class ServiceError(Exception):
    """Base for domain errors raised by services; mapped to HTTP responses in main.py."""


class AuthenticationError(ServiceError):
    pass


class NotFoundError(ServiceError):
    pass


class ConflictError(ServiceError):
    pass


class ValidationError(ServiceError):
    """A well-formed request that violates a business rule (e.g. password policy)."""
    pass
