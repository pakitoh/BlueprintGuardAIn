class DomainError(Exception):
    """Base class for all domain-related errors."""

    pass


class MappingError(DomainError):
    """Raised when an external payload cannot be mapped to a domain entity."""

    pass


class UnsupportedEventError(DomainError):
    """Raised when the webhook event type is one we deliberately do not process.

    Distinct from MappingError: the request is well-formed, we simply ignore it.
    """

    pass


class InfrastructureError(Exception):
    """Base class for infrastructure-related errors."""

    pass


class RepositoryError(InfrastructureError):
    """Raised when a repository operation fails."""

    pass
