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


class SubscriptionNotFound(ValidationError):
    """The payment rail reports the org's subscription doesn't exist (e.g. it was created
    in a different environment — sandbox vs live — or cancelled). Callers clear the stale
    link so the org can subscribe again."""
    pass
