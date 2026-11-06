"""Command line interface.

python -m app.cli seed
python -m app.cli eval --agent winloss-rag --version 1 --min-score 0.85
python -m app.cli eval --provider ollama --model llama3.2 --db sqlite://
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import select

from .agents.rag_agent import AgentConfig
from .agents.registry import add_version, get_agent, get_version
from .config import get_settings
from .db import Database
from .evals.harness import execute_eval_run
from .models import EvalDataset, EvalRun
from .rag.corpus import Corpus
from .seed import DEMO_SLUG, seed_all


def _open_database(url: str | None) -> tuple[Database, object]:
    settings = get_settings()
    db = Database(url or settings.database_url)
    db.create_all()
    seed_all(db, settings.data_dir)
    return db, settings


def cmd_seed(args: argparse.Namespace) -> int:
    db, settings = _open_database(args.db)
    print(f"Database ready at {db.url}")
    print(f"Documents: {len(Corpus.load(settings.data_dir / 'docs').documents)}")
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    db, settings = _open_database(args.db)
    corpus = Corpus.load(settings.data_dir / "docs")

    with db.session() as session:
        agent = get_agent(session, args.agent)
        if agent is None:
            print(f"Unknown agent '{args.agent}'", file=sys.stderr)
            return 2
        dataset = session.scalar(select(EvalDataset).where(EvalDataset.slug == args.dataset))
        if dataset is None:
            print(f"Unknown dataset '{args.dataset}'", file=sys.stderr)
            return 2

        version = get_version(agent, args.version)
        if version is None:
            print(f"Agent '{args.agent}' has no version {args.version}", file=sys.stderr)
            return 2
        if args.provider or args.model:
            config = AgentConfig(**version.config)
            config.provider = args.provider or config.provider
            config.model = args.model or config.model
            version = add_version(session, agent, config, note="created by the CLI")

        run = EvalRun(
            dataset_id=dataset.id,
            agent_version_id=version.id,
            status="queued",
            progress_total=len(dataset.cases),
        )
        session.add(run)
        session.flush()
        run_id = run.id
        provider, model = version.config["provider"], version.config["model"]
        label = f"{agent.slug} v{version.version} ({provider}/{model})"

    print(f"Evaluating {label} on '{args.dataset}'")
    summary = execute_eval_run(
        db,
        corpus,
        settings,
        run_id,
        on_case=lambda done, total: print(f"  {done}/{total}", end="\r", flush=True),
    )

    with db.session() as session:
        results = session.get(EvalRun, run_id).results
        failed = [r for r in results if not r.passed]

    print()
    print(f"mean score : {summary['mean_score']:.3f}")
    passed = summary["cases"] - len(failed)
    print(f"pass rate  : {summary['pass_rate']:.1%} ({passed}/{summary['cases']})")
    print(f"latency    : mean {summary['mean_latency_ms']} ms, p95 {summary['p95_latency_ms']} ms")
    print(f"statuses   : {summary['statuses']}")
    for name, value in summary["metrics"].items():
        print(f"  {name:<18} {value:.3f}")
    for result in failed:
        print(f"  FAILED {result.case_id}: score {result.score:.2f}, status {result.status}")

    if summary["mean_score"] < args.min_score:
        print(f"Gate failed: mean score {summary['mean_score']:.3f} < {args.min_score}")
        return 1
    if summary["pass_rate"] < args.min_pass_rate:
        print(f"Gate failed: pass rate {summary['pass_rate']:.3f} < {args.min_pass_rate}")
        return 1
    print("Gate passed")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent-lab")
    parser.add_argument("--db", help="database URL, for example sqlite:// for a throwaway database")
    sub = parser.add_subparsers(dest="command", required=True)

    seed = sub.add_parser("seed", help="create the database and load the demo data")
    seed.set_defaults(func=cmd_seed)

    ev = sub.add_parser("eval", help="run an evaluation and apply a quality gate")
    ev.add_argument("--agent", default=DEMO_SLUG)
    ev.add_argument("--dataset", default="winloss-qa")
    ev.add_argument("--version", type=int, default=None, help="default: latest version")
    ev.add_argument("--provider", help="evaluate with a different provider (creates a version)")
    ev.add_argument("--model", help="evaluate with a different model (creates a version)")
    ev.add_argument("--min-score", type=float, default=0.0)
    ev.add_argument("--min-pass-rate", type=float, default=0.0)
    ev.set_defaults(func=cmd_eval)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
