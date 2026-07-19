import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed

from linux_health.collectors.base import BaseCollector, Finding


def run_collectors(collectors: list[BaseCollector], tier: str = "fast", parallel: bool = True) -> list[Finding]:
    filtered = []
    for c in collectors:
        if tier == "fast" and c.tier not in ("fast",):
            continue
        if tier == "standard" and c.tier not in ("fast", "standard"):
            continue
        filtered.append(c)

    if not parallel or len(filtered) <= 1:
        return _run_sequential(filtered)

    all_findings: list[Finding] = []
    with ThreadPoolExecutor(max_workers=min(len(filtered), 4)) as executor:
        future_map = {executor.submit(_safe_collect, c): c for c in filtered}
        for future in as_completed(future_map):
            try:
                result = future.result(timeout=30)
                all_findings.extend(result)
            except Exception as exc:
                c = future_map[future]
                all_findings.append(Finding(
                    module=c.name,
                    title=f"{c.name} collector timed out",
                    detail=str(exc)[:200],
                    severity="info",
                    suggestion="Run lh --doctor for details",
                ))
    return all_findings


def _run_sequential(collectors: list[BaseCollector]) -> list[Finding]:
    all_findings: list[Finding] = []
    for c in collectors:
        try:
            all_findings.extend(_safe_collect(c))
        except Exception:
            all_findings.append(Finding(
                module=c.name,
                title=f"{c.name} collector failed",
                detail=traceback.format_exc()[-200:],
                severity="info",
                suggestion="Run lh --doctor for details",
            ))
    return all_findings


def _safe_collect(c: BaseCollector) -> list[Finding]:
    try:
        return c.collect()
    except Exception:
        return [Finding(
            module=c.name,
            title=f"{c.name} collector failed",
            detail=traceback.format_exc()[-200:],
            severity="info",
        )]
