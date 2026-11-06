"""The document corpus and the retriever on top of it."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .bm25 import BM25Index
from .chunking import Chunk, Document, chunk_document, extract_title


@dataclass(frozen=True)
class RetrievedChunk:
    chunk: Chunk
    score: float


class Corpus:
    def __init__(self, documents: list[Document]) -> None:
        self.documents = {doc.doc_id: doc for doc in documents}
        self.chunks: list[Chunk] = []
        for doc in documents:
            self.chunks.extend(chunk_document(doc))
        self._by_id = {chunk.chunk_id: chunk for chunk in self.chunks}
        self._index = BM25Index([chunk.text for chunk in self.chunks])

    @classmethod
    def load(cls, docs_dir: Path) -> Corpus:
        documents = []
        for path in sorted(Path(docs_dir).glob("*.md")):
            text = path.read_text(encoding="utf-8")
            documents.append(Document(path.stem, extract_title(text, path.stem), text))
        return cls(documents)

    def get_chunk(self, chunk_id: str) -> Chunk | None:
        return self._by_id.get(chunk_id)

    def get_document(self, doc_id: str) -> Document | None:
        return self.documents.get(doc_id)

    def search(self, query: str, top_k: int = 4) -> list[RetrievedChunk]:
        return [
            RetrievedChunk(self.chunks[i], score) for i, score in self._index.search(query, top_k)
        ]
