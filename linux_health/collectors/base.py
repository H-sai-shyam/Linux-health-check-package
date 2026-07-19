from dataclasses import dataclass, field
from abc import ABC, abstractmethod


@dataclass
class Finding:
    module: str = ""
    title: str = ""
    detail: str = ""
    severity: str = "info"
    confidence: int = 100
    impact: str = "low"
    expected: bool = False
    fixable: bool = False
    risk: str = "safe"
    category: str = "security"
    description: str = ""
    evidence: dict = field(default_factory=dict)
    suggestion: str = ""


SEVERITY_PENALTY = {"critical": 10, "warning": 5, "info": 2, "pass": 0}
IMPACT_MULTIPLIER = {"critical": 3.0, "high": 2.0, "medium": 1.5, "low": 1.0}


def calculate_finding_penalty(finding: Finding) -> float:
    base = SEVERITY_PENALTY.get(finding.severity, 0)
    if base == 0:
        return 0.0
    impact_mul = IMPACT_MULTIPLIER.get(finding.impact, 1.0)
    expected_mul = 0.2 if finding.expected else 1.0
    confidence_mul = finding.confidence / 100.0
    return round(base * impact_mul * expected_mul * confidence_mul, 1)


def scoring_summary(penalty: float) -> str:
    if penalty == 0:
        return "No impact"
    if penalty < 2:
        return "Negligible"
    if penalty < 5:
        return "Minor"
    if penalty < 10:
        return "Moderate"
    return "Significant"


class BaseCollector(ABC):
    name: str = ""
    tier: str = "fast"

    @abstractmethod
    def collect(self) -> list[Finding]:
        pass
