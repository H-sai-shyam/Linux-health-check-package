from linux_health.collectors.base import Finding
from linux_health.collectors.kernelcheck import KernelCheckCollector
from linux_health.collectors.malware import MalwareCollector
from linux_health.engine.runner import run_collectors
from linux_health.engine.scoring import calculate_score, categorize_findings, compute_overall_score


def run_all_checks(tier: str = "standard") -> dict:
    collectors = [
        KernelCheckCollector(),
        MalwareCollector(),
    ]

    findings = run_collectors(collectors, tier=tier)
    cat_scores = {}
    for cat, cat_findings in categorize_findings(findings).items():
        cat_scores[cat] = calculate_score(cat_findings)

    overall = compute_overall_score(cat_scores) if cat_scores else 100.0

    return {
        "findings": findings,
        "category_scores": cat_scores,
        "overall_score": overall,
        "severity_counts": {
            "critical": sum(1 for f in findings if f.severity == "critical"),
            "warning": sum(1 for f in findings if f.severity == "warning"),
            "info": sum(1 for f in findings if f.severity == "info"),
            "pass": sum(1 for f in findings if f.severity == "pass"),
        },
    }
