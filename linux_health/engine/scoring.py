from linux_health.collectors.base import Finding

SEVERITY_WEIGHTS = {
    "critical": 25,
    "warning": 10,
    "info": 2,
}

SEVERITY_CAPS = {
    "critical": 100,
    "warning": 50,
    "info": 10,
}


def calculate_score(findings: list[Finding]) -> float:
    deductions = 0
    for f in findings:
        weight = SEVERITY_WEIGHTS.get(f.severity, 0)
        cap = SEVERITY_CAPS.get(f.severity, 0)
        deductions = min(deductions + weight, cap)
    return max(0, 100 - deductions)


def categorize_findings(findings: list[Finding]) -> dict[str, list[Finding]]:
    cats: dict[str, list[Finding]] = {}
    for f in findings:
        cat = f.module.split(".")[0] if "." in f.module else f.module
        cats.setdefault(cat, []).append(f)
    return cats


def compute_category_scores(findings: list[Finding]) -> dict[str, float]:
    cats = categorize_findings(findings)
    return {cat: calculate_score(cats[cat]) for cat in cats}


def compute_overall_score(category_scores: dict[str, float]) -> float:
    if not category_scores:
        return 100.0
    return round(sum(category_scores.values()) / len(category_scores), 1)
