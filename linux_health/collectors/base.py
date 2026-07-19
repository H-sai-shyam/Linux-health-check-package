from dataclasses import dataclass, field
from abc import ABC, abstractmethod


@dataclass
class Finding:
    module: str = ""
    title: str = ""
    detail: str = ""
    severity: str = "info"
    evidence: dict = field(default_factory=dict)
    suggestion: str = ""


class BaseCollector(ABC):
    name: str = ""
    tier: str = "fast"

    @abstractmethod
    def collect(self) -> list[Finding]:
        pass
