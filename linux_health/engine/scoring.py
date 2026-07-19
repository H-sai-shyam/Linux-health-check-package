from linux_health.collectors.base import Finding, calculate_finding_penalty, scoring_summary

CATEGORY_PENALTY_CAP = 30.0


def calculate_score(findings: list[Finding]) -> float:
    total_penalty = 0.0
    for f in findings:
        total_penalty += calculate_finding_penalty(f)
    total_penalty = min(total_penalty, CATEGORY_PENALTY_CAP)
    return round(max(0, 100 - total_penalty), 1)


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


def get_scoring_details(findings: list[Finding]) -> list[dict]:
    details = []
    for f in findings:
        penalty = calculate_finding_penalty(f)
        if penalty > 0:
            details.append({
                "title": f.title,
                "severity": f.severity,
                "penalty": penalty,
                "impact": f.impact,
                "expected": f.expected,
                "impact_summary": scoring_summary(penalty),
            })
    return details
