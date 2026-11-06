from __future__ import annotations

import json

import pytest

from app.agents.rag_agent import AgentConfig, AgentResult, RagAgent
from app.config import Settings
from app.evals.compare import compare_results
from app.evals.datasets import DatasetError, sync_datasets, validate_dataset
from app.evals.harness import evaluate_case, execute_eval_run, percentile, summarize
from app.evals.metrics import (
    citation_recall,
    extract_numbers,
    fact_coverage,
    fact_matches,
    score_case,
    tool_correct,
)
from app.models import Agent, EvalDataset, EvalRun

# ---------------------------------------------------------------------- metrics


def test_extract_numbers_understands_units_and_separators():
    assert extract_numbers("EUR 4,200,000") == {4_200_000.0}
    assert extract_numbers("4.6 million") == {4_600_000.0}
    assert extract_numbers("about EUR 4.6M") == {4_600_000.0}
    assert extract_numbers("0.52 MPa and 12 months") == {0.52, 12.0}
    assert 6.0 in extract_numbers("There are 6 matching deals.")


@pytest.mark.parametrize(
    ("fact", "answer", "expected"),
    [
        ("4,600,000", "The average is EUR 4.6 million.", True),
        ("4,600,000", "The average is EUR 4,500,000.", False),
        ("6", "There are 6 deals", True),
        ("6", "There are 16 deals", False),
        ("0.52", "alarm at 0.52 MPa absolute", True),
        ("12 months", "Sample every 12 months.", True),
        ("12 months", "Sample every 13 months.", False),
        ("certification", "The Swiss Grid Certification mattered", True),
        ("3,850,000", "VoltEdge offered EUR 3850000", True),
    ],
)
def test_fact_matches(fact, answer, expected):
    assert fact_matches(fact, answer) is expected


def test_fact_coverage_and_helpers():
    assert fact_coverage(["a", "b"], "a only") == 0.5
    assert fact_coverage([], "anything") == 1.0
    assert citation_recall(["d1", "d2"], ["d1#0", "d3#1"]) == 0.5
    assert citation_recall([], []) == 1.0
    assert tool_correct(["x"], ["x", "y"]) == 1.0
    assert tool_correct(["x"], ["y"]) == 0.0


def make_result(**kwargs) -> AgentResult:
    defaults = {"question": "q", "answer": "", "status": "answered"}
    return AgentResult(**{**defaults, **kwargs})


def test_score_case_perfect_answer():
    case = {
        "id": "c",
        "question": "q",
        "expected_facts": ["12 months"],
        "expected_docs": ["d1"],
        "expected_tools": ["search_documents"],
    }
    result = make_result(
        answer="Every 12 months [d1#0].",
        citations=["d1#0"],
        tool_calls=[{"type": "tool", "name": "search_documents", "retrieved": ["d1#0"]}],
    )
    scored = score_case(case, result)
    assert scored.score == 1.0 and scored.passed
    assert scored.metrics["retrieval_recall"] == 1.0


def test_score_case_wrong_fact_fails():
    case = {"id": "c", "question": "q", "expected_facts": ["12 months"], "expected_docs": ["d1"]}
    result = make_result(answer="Every 6 months [d1#0].", citations=["d1#0"])
    scored = score_case(case, result)
    assert scored.score == pytest.approx(0.6)
    assert not scored.passed


def test_score_case_refusal_cases():
    case = {"id": "c", "question": "q", "should_refuse": True}
    assert score_case(case, make_result(status="refused")).passed
    assert score_case(case, make_result(status="rejected")).score == 0.5
    assert not score_case(case, make_result(status="answered", answer="made up")).passed


def test_score_case_error_is_zero():
    case = {"id": "c", "question": "q", "expected_facts": ["x"]}
    scored = score_case(case, make_result(status="error"))
    assert scored.score == 0.0 and not scored.passed


# --------------------------------------------------------------------- datasets


def test_dataset_validation():
    with pytest.raises(DatasetError):
        validate_dataset({"slug": "x", "name": "x"})
    with pytest.raises(DatasetError):
        validate_dataset({"slug": "x", "name": "x", "cases": [{"id": "a", "question": "q"}]})
    with pytest.raises(DatasetError):
        validate_dataset(
            {
                "slug": "x",
                "name": "x",
                "cases": [
                    {"id": "a", "question": "q", "should_refuse": True},
                    {"id": "a", "question": "q2", "should_refuse": True},
                ],
            }
        )


def test_shipped_dataset_is_valid(data_dir, corpus):
    data = json.loads((data_dir / "evals" / "winloss_qa.json").read_text(encoding="utf-8"))
    validate_dataset(data)
    assert len(data["cases"]) == 20
    for case in data["cases"]:
        for doc_id in case.get("expected_docs", []):
            assert corpus.get_document(doc_id), f"{case['id']} expects unknown doc {doc_id}"


def test_sync_datasets_is_idempotent(db, data_dir):
    assert sync_datasets(db, data_dir) == 1
    assert sync_datasets(db, data_dir) == 1
    with db.session() as session:
        assert session.query(EvalDataset).count() == 1


# ---------------------------------------------------------------------- harness


def test_percentile_and_summarize():
    assert percentile([1, 2, 3, 4, 5], 50) == 3
    assert percentile([], 95) == 0.0
    rows = [
        {
            "score": 1.0,
            "passed": True,
            "latency_ms": 10,
            "tokens": 5,
            "status": "answered",
            "metrics": {"fact_coverage": 1.0},
        },
        {
            "score": 0.5,
            "passed": False,
            "latency_ms": 30,
            "tokens": 7,
            "status": "rejected",
            "metrics": {"fact_coverage": 0.0},
        },
    ]
    summary = summarize(rows)
    assert summary["mean_score"] == 0.75
    assert summary["pass_rate"] == 0.5
    assert summary["total_tokens"] == 12
    assert summary["statuses"] == {"answered": 1, "rejected": 1}
    assert summary["metrics"]["fact_coverage"] == 0.5


def load_cases(data_dir) -> list[dict]:
    return json.loads((data_dir / "evals" / "winloss_qa.json").read_text(encoding="utf-8"))["cases"]


def run_all(toolbox, data_dir, model: str) -> list[dict]:
    agent = RagAgent(AgentConfig(model=model), toolbox, Settings())
    return [evaluate_case(agent, case) for case in load_cases(data_dir)]


def test_mock_extractive_scores_high_on_the_shipped_dataset(toolbox, data_dir):
    results = run_all(toolbox, data_dir, "mock-extractive")
    failed = [(r["case_id"], r["score"], r["answer"][:120]) for r in results if not r["passed"]]
    summary = summarize(results)
    assert summary["pass_rate"] >= 0.9, failed
    assert summary["mean_score"] >= 0.9, failed


def test_mock_sloppy_scores_clearly_lower_and_regressions_are_found(toolbox, data_dir):
    good = run_all(toolbox, data_dir, "mock-extractive")
    bad = run_all(toolbox, data_dir, "mock-sloppy")
    assert summarize(bad)["mean_score"] < summarize(good)["mean_score"] - 0.1
    comparison = compare_results(good, bad)
    assert comparison["regressions"]
    assert comparison["mean_delta"] < 0
    assert comparison["improvements"] == [] or len(comparison["improvements"]) < len(
        comparison["regressions"]
    )


def test_execute_eval_run_stores_results_and_summary(db, corpus, data_dir):
    from app.agents.registry import create_agent

    sync_datasets(db, data_dir)
    with db.session() as session:
        agent = create_agent(session, "a", "A", "", AgentConfig())
        dataset = session.query(EvalDataset).one()
        run = EvalRun(dataset_id=dataset.id, agent_version_id=agent.versions[0].id)
        session.add(run)
        session.flush()
        run_id = run.id

    seen: list[int] = []
    summary = execute_eval_run(db, corpus, Settings(), run_id, on_case=lambda i, n: seen.append(i))
    assert seen[-1] == 20

    with db.session() as session:
        run = session.get(EvalRun, run_id)
        assert run.status == "completed"
        assert run.progress_done == run.progress_total == 20
        assert len(run.results) == 20
        assert run.summary["mean_score"] == summary["mean_score"]
        assert session.query(Agent).count() == 1


def test_eval_run_with_unreachable_provider_ends_as_completed_with_error_cases(
    db, corpus, data_dir
):
    """Provider failures are scored as 0 per case, they do not crash the run."""
    from app.agents.registry import create_agent

    cases = load_cases(data_dir)[:2]
    with db.session() as session:
        agent = create_agent(session, "b", "B", "", AgentConfig(provider="ollama", model="x"))
        dataset = EvalDataset(slug="tiny", name="tiny", kind="qa", cases=cases)
        session.add(dataset)
        session.flush()
        run = EvalRun(dataset_id=dataset.id, agent_version_id=agent.versions[0].id)
        session.add(run)
        session.flush()
        run_id = run.id

    settings = Settings(ollama_url="http://127.0.0.1:9", request_timeout_s=1)
    summary = execute_eval_run(db, corpus, settings, run_id)
    assert summary["statuses"] == {"error": 2}
    assert summary["mean_score"] == 0.0
    assert summary["pass_rate"] == 0.0
