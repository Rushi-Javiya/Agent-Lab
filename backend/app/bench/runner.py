"""Run the same prompts against several models and measure latency, speed and quality."""

from __future__ import annotations

import json
import statistics
from datetime import UTC, datetime
from pathlib import Path

from ..agents.prompts import DEFAULT_SYSTEM_PROMPT, build_answer_prompt
from ..config import Settings
from ..db import Database
from ..evals.harness import percentile
from ..evals.metrics import fact_coverage
from ..models import BenchmarkResult, BenchmarkRun
from ..providers import ChatMessage, ProviderError, get_provider
from ..rag.citations import validate_answer
from ..rag.corpus import Corpus

CONTEXT_CHUNKS = 2


def load_prompt_set(data_dir: Path, slug: str) -> dict:
    path = Path(data_dir) / "bench" / f"{slug}.json"
    if not path.exists():
        raise FileNotFoundError(f"Unknown prompt set '{slug}'")
    return json.loads(path.read_text(encoding="utf-8"))


def list_prompt_sets(data_dir: Path) -> list[dict]:
    sets = []
    for path in sorted((Path(data_dir) / "bench").glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        sets.append(
            {
                "slug": data["slug"],
                "name": data["name"],
                "description": data.get("description", ""),
                "prompts": len(data["prompts"]),
            }
        )
    return sets


def build_prompts(corpus: Corpus, prompt_set: dict) -> list[dict]:
    """Attach the retrieved context to every question, like the RAG agent does."""
    prepared = []
    for item in prompt_set["prompts"]:
        hits = corpus.search(item["question"], CONTEXT_CHUNKS)
        blocks = [f"[{h.chunk.chunk_id}]\n{h.chunk.text}" for h in hits]
        prepared.append(
            {
                "id": item["id"],
                "prompt": build_answer_prompt(item["question"], blocks, []),
                "expected_facts": item.get("expected_facts", []),
                "chunk_ids": {h.chunk.chunk_id for h in hits},
                "doc_ids": {h.chunk.doc_id for h in hits},
            }
        )
    return prepared


def compute_stats(samples: list[dict], errors: list[str]) -> dict:
    """Aggregate the samples of one target. A sample has latency, tokens, speed and quality."""
    if not samples:
        return {"calls": 0, "errors": len(errors), "error_sample": errors[:1]}
    latencies = [s["latency_ms"] for s in samples]
    speeds = [s["tokens_per_second"] for s in samples if s["tokens_per_second"]]
    return {
        "calls": len(samples),
        "errors": len(errors),
        "error_sample": errors[:1],
        "latency_p50_ms": round(percentile(latencies, 50), 1),
        "latency_p95_ms": round(percentile(latencies, 95), 1),
        "latency_mean_ms": round(statistics.fmean(latencies), 1),
        "tokens_per_second": round(statistics.fmean(speeds), 1) if speeds else None,
        "completion_tokens_mean": round(
            statistics.fmean(s["completion_tokens"] for s in samples), 1
        ),
        "fact_coverage": round(statistics.fmean(s["fact_coverage"] for s in samples), 4),
        "grounded_rate": round(statistics.fmean(1.0 if s["grounded"] else 0.0 for s in samples), 4),
    }


def execute_benchmark_run(db: Database, corpus: Corpus, settings: Settings, run_id: int) -> None:
    with db.session() as session:
        run = session.get(BenchmarkRun, run_id)
        repeats = run.repeats
        prompt_set_slug = run.prompt_set
        targets = [(r.id, r.provider, r.model) for r in run.results]
        run.status = "running"

    try:
        prompts = build_prompts(corpus, load_prompt_set(settings.data_dir, prompt_set_slug))
        total = len(targets) * repeats * len(prompts)
        done = 0
        with db.session() as session:
            session.get(BenchmarkRun, run_id).progress_total = total

        for result_id, provider_name, model in targets:
            provider = get_provider(provider_name, settings)
            samples: list[dict] = []
            errors: list[str] = []

            if provider_name != "mock":
                try:  # warm-up so that model loading time does not distort the first sample
                    provider.chat(model, [ChatMessage("user", "Say OK.")], max_tokens=8)
                except ProviderError as exc:
                    errors.append(str(exc))

            for _ in range(repeats):
                for item in prompts:
                    try:
                        reply = provider.chat(
                            model,
                            [
                                ChatMessage("system", DEFAULT_SYSTEM_PROMPT),
                                ChatMessage("user", item["prompt"]),
                            ],
                            temperature=0.0,
                        )
                        validation = validate_answer(reply.text, item["chunk_ids"], item["doc_ids"])
                        samples.append(
                            {
                                "latency_ms": reply.latency_ms,
                                "tokens_per_second": reply.tokens_per_second,
                                "completion_tokens": reply.completion_tokens,
                                "fact_coverage": fact_coverage(item["expected_facts"], reply.text),
                                "grounded": validation.valid and bool(validation.citations),
                            }
                        )
                    except ProviderError as exc:
                        errors.append(str(exc))
                    done += 1
                    with db.session() as session:
                        session.get(BenchmarkRun, run_id).progress_done = done

            stats = compute_stats(samples, errors)
            with db.session() as session:
                result = session.get(BenchmarkResult, result_id)
                result.stats = stats
                result.error = errors[0] if errors and not samples else None

        with db.session() as session:
            run = session.get(BenchmarkRun, run_id)
            run.status = "completed"
            run.finished_at = datetime.now(UTC)
    except Exception as exc:  # noqa: BLE001 - mark the run as failed whatever happened
        with db.session() as session:
            run = session.get(BenchmarkRun, run_id)
            run.status = "failed"
            run.error = f"{type(exc).__name__}: {exc}"
            run.finished_at = datetime.now(UTC)
        raise
