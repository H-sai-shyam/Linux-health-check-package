import traceback
from linux_health.collectors.base import BaseCollector, Finding


def run_collectors(collectors: list[BaseCollector], tier: str = "fast") -> list[Finding]:
    all_findings: list[Finding] = []
    for c in collectors:
        if tier == "fast" and c.tier not in ("fast",):
            continue
        if tier == "standard" and c.tier not in ("fast", "standard"):
            continue
        try:
            findings = c.collect()
            all_findings.extend(findings)
        except Exception:
            all_findings.append(Finding(
                module=c.name,
                title=f"{c.name} collector failed",
                detail=traceback.format_exc()[-200:],
                severity="info",
                suggestion="Run lh --doctor for details",
            ))
    return all_findings
