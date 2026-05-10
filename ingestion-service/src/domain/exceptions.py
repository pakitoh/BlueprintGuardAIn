class DomainError(Exception):
    """Base class for all domain-related errors."""

    pass


class MappingError(DomainError):
    """Raised when an external payload cannot be mapped to a domain entity."""

    pass


class InfrastructureError(Exception):
    """Base class for infrastructure-related errors."""

    pass


class RepositoryError(InfrastructureError):
    """Raised when a repository operation fails."""

    pass
