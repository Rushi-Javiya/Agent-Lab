"""Compare two evaluation runs case by case, to spot regressions between agent versions."""

from __future__ import annotations


def compare_results(run_a: list[dict], run_b: list[dict]) -> dict:
    """`run_a` is the baseline, `run_b` the candidate. Both are lists of result dicts."""
    by_id_a = {r["case_id"]: r for r in run_a}
    by_id_b = {r["case_id"]: r for r in run_b}

    cases = []
    regressions, improvements = [], []
    for case_id in by_id_a:
        a = by_id_a[case_id]
        b = by_id_b.get(case_id)
        if b is None:
            continue
        delta = round(b["score"] - a["score"], 4)
        entry = {
            "case_id": case_id,
            "question": a["question"],
            "score_a": a["score"],
            "score_b": b["score"],
            "delta": delta,
            "passed_a": a["passed"],
            "passed_b": b["passed"],
            "status_a": a["status"],
            "status_b": b["status"],
        }
        cases.append(entry)
        if a["passed"] and not b["passed"]:
            regressions.append(case_id)
        elif b["passed"] and not a["passed"]:
            improvements.append(case_id)

    mean_a = sum(c["score_a"] for c in cases) / len(cases) if cases else 0.0
    mean_b = sum(c["score_b"] for c in cases) / len(cases) if cases else 0.0
    return {
        "cases": cases,
        "regressions": regressions,
        "improvements": improvements,
        "mean_score_a": round(mean_a, 4),
        "mean_score_b": round(mean_b, 4),
        "mean_delta": round(mean_b - mean_a, 4),
    }
