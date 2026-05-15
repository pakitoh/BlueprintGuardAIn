class DomainError(Exception):
    """Base class for domain exceptions."""

    pass


class RepositoryError(DomainError):
    """Raised when an infrastructure repository fails."""

    pass
