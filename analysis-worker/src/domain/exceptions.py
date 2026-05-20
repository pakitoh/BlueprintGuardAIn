class DomainError(Exception):
    pass


class RepositoryError(DomainError):
    pass


class EmptyFindingsError(DomainError):
    pass


class DuplicateFindingsError(DomainError):
    def __init__(self, pairs: list[tuple[str, str]]):
        self.pairs = pairs
