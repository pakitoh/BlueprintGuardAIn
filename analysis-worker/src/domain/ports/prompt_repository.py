from abc import ABC, abstractmethod


class PromptRepository(ABC):
    @abstractmethod
    def compile(self, variables: dict[str, str]) -> str:
        ...
