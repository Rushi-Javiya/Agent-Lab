from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.db import Database
from app.main import create_app


@pytest.fixture()
def client(corpus, data_dir, monkeypatch):
    monkeypatch.setattr(
        "app.api.routes_agents.provider_status",
        lambda settings: {"mock": {"available": True, "models": ["mock-extractive"]}},
    )
    app = create_app(Settings(data_dir=data_dir), Database("sqlite://"), corpus)
    return TestClient(app)


# ------------------------------------------------------------------------ basics


def test_runs_left_running_by_a_stopped_server_are_marked_failed(corpus, data_dir):
    from app.models import BenchmarkRun, EvalDataset, EvalRun

    db = Database("sqlite://")
    create_app(Settings(data_dir=data_dir), db, corpus)
    with db.session() as session:
        dataset = session.query(EvalDataset).one()
        session.add(EvalRun(dataset_id=dataset.id, agent_version_id=1, status="running"))
        session.add(BenchmarkRun(prompt_set="qa-short", status="queued"))

    restarted = TestClient(create_app(Settings(data_dir=data_dir), db, corpus))
    run = restarted.get("/api/evals/runs/1").json()
    assert run["status"] == "failed"
    assert "restart" in run["error"]
    assert restarted.get("/api/benchmarks/runs/1").json()["status"] == "failed"


def test_default_urls_avoid_the_slow_localhost_lookup():
    settings = Settings()
    assert "localhost" not in settings.ollama_url
    assert "localhost" not in settings.llamacpp_url


def test_health(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["providers"]["mock"]["available"] is True


def test_seeded_demo_agent(client):
    agents = client.get("/api/agents").json()
    assert [a["slug"] for a in agents] == ["winloss-rag"]
    assert agents[0]["version_count"] == 2
    assert agents[0]["latest_version"]["config"]["model"] == "mock-sloppy"


def test_create_agent_and_versions(client):
    body = {
        "slug": "my-agent",
        "name": "My agent",
        "config": {"provider": "mock", "model": "mock-extractive", "top_k": 3},
    }
    created = client.post("/api/agents", json=body)
    assert created.status_code == 201
    assert created.json()["versions"][0]["version"] == 1

    assert client.post("/api/agents", json=body).status_code == 409

    version = client.post(
        "/api/agents/my-agent/versions",
        json={"config": {"provider": "mock", "model": "mock-sloppy"}, "note": "weaker"},
    )
    assert version.status_code == 201
    assert version.json()["version"] == 2

    detail = client.get("/api/agents/my-agent").json()
    assert [v["version"] for v in detail["versions"]] == [1, 2]
    assert detail["versions"][0]["config"]["top_k"] == 3


def test_agent_validation_errors(client):
    bad_slug = {"slug": "Bad Slug!", "name": "x"}
    assert client.post("/api/agents", json=bad_slug).status_code == 422
    bad_provider = {"slug": "good-slug", "name": "x", "config": {"provider": "nope"}}
    assert client.post("/api/agents", json=bad_provider).status_code == 422
    bad_top_k = {"slug": "good-slug", "name": "x", "config": {"top_k": 99}}
    assert client.post("/api/agents", json=bad_top_k).status_code == 422
    assert client.get("/api/agents/missing").status_code == 404


# -------------------------------------------------------------------------- runs


def test_run_agent_and_list_runs(client):
    response = client.post(
        "/api/agents/winloss-rag/run",
        json={"question": "How many deals did we lose?", "version": 1},
    )
    assert response.status_code == 200
    run = response.json()
    assert run["status"] == "answered"
    assert "6" in run["answer"]
    assert run["version"] == 1
    assert [c["type"] for c in run["tool_calls"]] == ["route", "tool"]

    runs = client.get("/api/agents/winloss-rag/runs").json()
    assert len(runs) == 1 and runs[0]["id"] == run["id"]


def test_timestamps_are_explicit_utc(client):
    agent = client.get("/api/agents/winloss-rag").json()
    assert agent["created_at"].endswith("+00:00")
    run = client.post(
        "/api/agents/winloss-rag/run", json={"question": "How many deals did we lose?"}
    )
    assert run.json()["created_at"].endswith("+00:00")
    eval_run = client.get(f"/api/evals/runs/{start_eval(client, 1)['id']}").json()
    assert eval_run["created_at"].endswith("+00:00")
    assert eval_run["finished_at"].endswith("+00:00")


def test_run_agent_not_found_cases(client):
    assert client.post("/api/agents/nope/run", json={"question": "x"}).status_code == 404
    missing_version = client.post(
        "/api/agents/winloss-rag/run", json={"question": "x", "version": 9}
    )
    assert missing_version.status_code == 404
    assert client.post("/api/agents/winloss-rag/run", json={"question": ""}).status_code == 422


# ------------------------------------------------------------------------- evals


def start_eval(client, version: int) -> dict:
    response = client.post(
        "/api/evals/runs",
        json={"dataset": "winloss-qa", "agent": "winloss-rag", "version": version},
    )
    assert response.status_code == 202
    return response.json()


def test_datasets(client):
    datasets = client.get("/api/datasets").json()
    assert datasets[0]["slug"] == "winloss-qa" and datasets[0]["case_count"] == 20
    detail = client.get("/api/datasets/winloss-qa").json()
    assert len(detail["cases"]) == 20
    assert client.get("/api/datasets/none").status_code == 404


def test_eval_run_flow_and_agent_summary(client):
    started = start_eval(client, 1)
    run = client.get(f"/api/evals/runs/{started['id']}").json()
    assert run["status"] == "completed"
    assert run["progress"] == {"done": 20, "total": 20}
    assert len(run["results"]) == 20
    assert run["summary"]["mean_score"] >= 0.9
    assert run["version"] == 1

    summary = client.get("/api/agents/winloss-rag").json()
    assert summary["versions"][0]["latest_eval"]["mean_score"] == run["summary"]["mean_score"]
    assert summary["versions"][1]["latest_eval"] is None

    listed = client.get("/api/evals/runs", params={"agent": "winloss-rag"}).json()
    assert [r["id"] for r in listed] == [started["id"]]


def test_compare_versions_finds_regressions(client):
    good = start_eval(client, 1)["id"]
    bad = start_eval(client, 2)["id"]
    comparison = client.get(
        "/api/evals/compare", params={"baseline": good, "candidate": bad}
    ).json()
    assert comparison["mean_delta"] < 0
    assert comparison["regressions"]
    assert comparison["baseline"]["version"] == 1 and comparison["candidate"]["version"] == 2
    assert "results" not in comparison["baseline"]


def test_eval_run_errors(client):
    ok = {"dataset": "winloss-qa", "agent": "winloss-rag"}
    assert client.post("/api/evals/runs", json={**ok, "dataset": "x"}).status_code == 404
    assert client.post("/api/evals/runs", json={**ok, "agent": "x"}).status_code == 404
    assert client.post("/api/evals/runs", json={**ok, "version": 7}).status_code == 404
    assert client.get("/api/evals/runs/999").status_code == 404
    assert (
        client.get("/api/evals/compare", params={"baseline": 1, "candidate": 2}).status_code == 404
    )


# -------------------------------------------------------------------- benchmarks


def test_benchmark_flow(client):
    assert client.get("/api/benchmarks/prompt-sets").json()[0]["slug"] == "qa-short"
    response = client.post(
        "/api/benchmarks/runs",
        json={
            "targets": [
                {"provider": "mock", "model": "mock-extractive"},
                {"provider": "mock", "model": "mock-sloppy"},
            ],
            "repeats": 1,
        },
    )
    assert response.status_code == 202
    run = client.get(f"/api/benchmarks/runs/{response.json()['id']}").json()
    assert run["status"] == "completed"
    good, bad = (r["stats"] for r in run["results"])
    assert good["fact_coverage"] > bad["fact_coverage"]
    assert len(client.get("/api/benchmarks/runs").json()) == 1


def test_benchmark_validation(client):
    bad_provider = {"targets": [{"provider": "nope", "model": "m"}]}
    assert client.post("/api/benchmarks/runs", json=bad_provider).status_code == 422
    assert client.post("/api/benchmarks/runs", json={"targets": []}).status_code == 422
    unknown_set = {"targets": [{"provider": "mock", "model": "mock-extractive"}], "prompt_set": "x"}
    assert client.post("/api/benchmarks/runs", json=unknown_set).status_code == 404
    assert client.get("/api/benchmarks/runs/99").status_code == 404


# ---------------------------------------------------------- documents and records


def test_documents_search_and_records(client):
    documents = client.get("/api/documents").json()
    assert len(documents) == 16
    detail = client.get("/api/documents/wl-001-nordgrid").json()
    assert detail["title"].startswith("Win/Loss Report")
    assert detail["chunks"][0]["chunk_id"] == "wl-001-nordgrid#0"
    assert client.get("/api/documents/nope").status_code == 404

    hits = client.get("/api/search", params={"q": "transformer oil sampling"}).json()
    assert hits[0]["doc_id"] == "mm-transformer-oil"

    records = client.get("/api/records").json()
    assert len(records) == 12 and records[0]["method"] == "reference"


def test_extraction_endpoint_scores_and_can_apply(client):
    report = client.post("/api/records/extract", json={"method": "rules"}).json()
    assert report["applied"] == 0
    assert report["overall_accuracy"] < 0.9

    applied = client.post("/api/records/extract", json={"method": "rules", "apply": True}).json()
    assert applied["applied"] == 12
    methods = {r["method"] for r in client.get("/api/records").json()}
    assert methods == {"rules"}
    # narrative reports lost their competitor, so the records tool now sees fewer rows
    run = client.post(
        "/api/agents/winloss-rag/run",
        json={"question": "How many deals did we win against Altrix?", "version": 1},
    ).json()
    assert "There are 2 matching deals" in run["answer"]


def test_extraction_rejects_unknown_provider(client):
    response = client.post("/api/records/extract", json={"method": "llm", "provider": "nope"})
    assert response.status_code == 422
