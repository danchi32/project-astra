class ServiceError(Exception):
    """Base for errors this service maps onto HTTP status codes in main.py."""


class ValidationError(ServiceError):
    """The request was well-formed but asks for something impossible. → 422"""


class NotFoundError(ServiceError):
    """The addressed resource does not exist. → 404"""


class NotConfiguredError(ServiceError):
    """An integration the request needs has not been given its credentials. → 503

    Distinct from a failure: nothing is broken, the operator simply has not set the
    environment variable yet. Kept separate so a missing Telegram token reads as "not set
    up" in the logs rather than as an outage.
    """
