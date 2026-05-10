class DomainError(Exception):
    """Base class for all domain-related errors."""
    pass

class MappingError(DomainError):
    """Raised when an external payload cannot be mapped to a domain entity."""
    pass
