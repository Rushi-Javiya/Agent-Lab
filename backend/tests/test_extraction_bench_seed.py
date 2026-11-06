from __future__ import annotations

import pytest

from app.agents.extraction import clean_extraction, evaluate_extraction, load_truth
from app.bench.runner import (
    build_prompts,
    compute_stats,
    execute_benchmark_run,
    list_prompt_sets,
    load_prompt_set,
)
from app.config import Settings
from app.models import (
    Agent,
    BenchmarkResult,
    BenchmarkRun,
    EvalDataset,
    WinLossRecord,
)
from app.seed import seed_all

# ------------------------------------------------------------------- extraction


def test_clean_extraction_normalises_model_output():
    cleaned = clean_extraction(
        {
            "customer": " Acme ",
            "region": None,
            "deal_date": "2025-01-31",
            "outcome": "LOST",
            "our_price_eur": "EUR 3.9 million",
            "competitor": "null",
            "competitor_price_eur": "3,600,000",
            "reason_category": "Lead Time",
        }
    )
    assert cleaned["customer"] == "Acme"
    assert cleaned["region"] is None
    assert cleaned["outcome"] == "lost"
    assert cleaned["our_price_eur"] == 3_900_000
    assert cleaned["competitor_price_eur"] == 3_600_000
    assert cleaned["competitor"] is None
    assert cleaned["reason_category"] == "lead_time"


def test_clean_extraction_rejects_empty_and_bad_values():
    assert clean_extraction({}) is None
    cleaned = clean_extraction({"customer": "X", "outcome": "draw", "reason_category": "mood"})
    assert cleaned["outcome"] is None and cleaned["reason_category"] is None


def test_rules_extraction_beats_nothing_but_misses_narrative_reports(corpus, data_dir):
    report = evaluate_extraction(corpus, load_truth(data_dir), "rules", Settings())
    accuracy = report["field_accuracy"]
    assert accuracy["customer"] == 1.0
    assert accuracy["outcome"] == 1.0
    assert accuracy["our_price_eur"] == pytest.approx(8 / 12, abs=1e-3)  # structured reports only
    assert report["overall_accuracy"] < 0.9
    narrative = [d for d in report["documents"] if d["doc_id"] == "wl-009-tasman"][0]
    assert narrative["fields"]["competitor"]["correct"] is False


def test_llm_extraction_flow_with_the_mock_model(corpus, data_dir):
    report = evaluate_extraction(
        corpus, load_truth(data_dir), "llm", Settings(), "mock", "mock-extractive"
    )
    assert report["method"] == "llm" and report["model"] == "mock-extractive"
    sloppy = evaluate_extraction(
        corpus, load_truth(data_dir), "llm", Settings(), "mock", "mock-sloppy"
    )
    assert sloppy["field_accuracy"]["our_price_eur"] == 0.0
    assert report["overall_accuracy"] > sloppy["overall_accuracy"]


def test_extraction_reports_provider_errors_per_document(corpus, data_dir, unreachable):
    report = evaluate_extraction(corpus, load_truth(data_dir)[:1], "llm", Settings(), "ollama", "x")
    assert report["documents"][0]["error"]
    assert report["overall_accuracy"] == 0.0


# --------------------------------------------------------------------- benchmark


def test_compute_stats():
    samples = [
        {
            "latency_ms": 100,
            "tokens_per_second": 50,
            "completion_tokens": 20,
            "fact_coverage": 1.0,
            "grounded": True,
        },
        {
            "latency_ms": 300,
            "tokens_per_second": 30,
            "completion_tokens": 40,
            "fact_coverage": 0.0,
            "grounded": False,
        },
    ]
    stats = compute_stats(samples, [])
    assert stats["latency_p50_ms"] == 200
    assert stats["tokens_per_second"] == 40
    assert stats["fact_coverage"] == 0.5
    assert stats["grounded_rate"] == 0.5
    assert compute_stats([], ["boom"])["errors"] == 1


def test_prompt_sets_load_and_get_context(corpus, data_dir):
    assert [s["slug"] for s in list_prompt_sets(data_dir)] == ["qa-short"]
    prompts = build_prompts(corpus, load_prompt_set(data_dir, "qa-short"))
    assert len(prompts) == 8
    assert all(p["prompt"].startswith("TASK:rag_answer") and p["chunk_ids"] for p in prompts)


def test_benchmark_run_with_mock_models(db, corpus, data_dir):
    with db.session() as session:
        run = BenchmarkRun(prompt_set="qa-short", repeats=2)
        run.results = [
            BenchmarkResult(provider="mock", model="mock-extractive"),
            BenchmarkResult(provider="mock", model="mock-sloppy"),
        ]
        session.add(run)
        session.flush()
        run_id = run.id

    execute_benchmark_run(db, corpus, Settings(data_dir=data_dir), run_id)

    with db.session() as session:
        run = session.get(BenchmarkRun, run_id)
        assert run.status == "completed"
        assert run.progress_done == run.progress_total == 2 * 2 * 8
        good, bad = (r.stats for r in run.results)
        assert good["calls"] == 16
        assert good["fact_coverage"] > bad["fact_coverage"]
        assert good["grounded_rate"] > bad["grounded_rate"]


def test_benchmark_records_unreachable_server_as_errors(db, corpus, data_dir, unreachable):
    with db.session() as session:
        run = BenchmarkRun(prompt_set="qa-short", repeats=1)
        run.results = [BenchmarkResult(provider="ollama", model="x")]
        session.add(run)
        session.flush()
        run_id = run.id
    execute_benchmark_run(db, corpus, Settings(data_dir=data_dir), run_id)
    with db.session() as session:
        result = session.get(BenchmarkRun, run_id).results[0]
        assert result.stats["calls"] == 0
        assert result.error


# ------------------------------------------------------------------------- seed


def test_seed_is_idempotent_and_complete(db, data_dir):
    first = seed_all(db, data_dir)
    second = seed_all(db, data_dir)
    assert first["records"] == 12 and first["demo_agent_created"] is True
    assert second["demo_agent_created"] is False
    with db.session() as session:
        assert session.query(Agent).count() == 1
        assert len(session.query(Agent).one().versions) == 2
        assert session.query(EvalDataset).count() == 1
        assert session.query(WinLossRecord).count() == 12
