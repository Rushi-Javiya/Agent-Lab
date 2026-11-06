"""Evaluation datasets are JSON files in data/evals and are synced into the database."""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select

from ..db import Database
from ..models import EvalDataset


class DatasetError(ValueError):
    pass


def validate_dataset(data: dict) -> None:
    for key in ("slug", "name", "cases"):
        if key not in data:
            raise DatasetError(f"dataset is missing '{key}'")
    seen: set[str] = set()
    for case in data["cases"]:
        if "id" not in case or "question" not in case:
            raise DatasetError("every case needs an 'id' and a 'question'")
        if case["id"] in seen:
            raise DatasetError(f"duplicate case id '{case['id']}'")
        seen.add(case["id"])
        if not case.get("should_refuse") and not case.get("expected_facts"):
            raise DatasetError(f"case '{case['id']}' needs expected_facts or should_refuse")


def sync_datasets(db: Database, data_dir: Path) -> int:
    """Insert or update every dataset file. Returns the number of datasets."""
    files = sorted((Path(data_dir) / "evals").glob("*.json"))
    with db.session() as session:
        for path in files:
            data = json.loads(path.read_text(encoding="utf-8"))
            validate_dataset(data)
            dataset = session.scalar(select(EvalDataset).where(EvalDataset.slug == data["slug"]))
            if dataset is None:
                dataset = EvalDataset(slug=data["slug"])
                session.add(dataset)
            dataset.name = data["name"]
            dataset.kind = data.get("kind", "qa")
            dataset.description = data.get("description", "")
            dataset.cases = data["cases"]
    return len(files)
