"""Split markdown documents into chunks that can be cited as `doc_id#index`."""

from __future__ import annotations

import re
from dataclasses import dataclass

MAX_CHUNK_CHARS = 700


@dataclass(frozen=True)
class Document:
    doc_id: str
    title: str
    text: str

    @property
    def kind(self) -> str:
        return "winloss" if self.doc_id.startswith("wl-") else "manual"


@dataclass(frozen=True)
class Chunk:
    doc_id: str
    index: int
    text: str

    @property
    def chunk_id(self) -> str:
        return f"{self.doc_id}#{self.index}"


def extract_title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return fallback


def split_paragraphs(text: str) -> list[str]:
    parts = re.split(r"\n\s*\n", text.strip())
    return [part.strip() for part in parts if part.strip()]


def chunk_document(document: Document, max_chars: int = MAX_CHUNK_CHARS) -> list[Chunk]:
    """Greedy paragraph packing. Headings stay together with the paragraph that follows them."""
    paragraphs = split_paragraphs(document.text)

    merged: list[str] = []
    pending_heading: list[str] = []
    for paragraph in paragraphs:
        if paragraph.startswith("#") and "\n" not in paragraph:
            pending_heading.append(paragraph)
            continue
        merged.append("\n".join([*pending_heading, paragraph]))
        pending_heading = []
    if pending_heading:
        merged.append("\n".join(pending_heading))

    chunks: list[Chunk] = []
    current = ""
    for block in merged:
        if current and len(current) + len(block) + 2 > max_chars:
            chunks.append(Chunk(document.doc_id, len(chunks), current))
            current = block
        else:
            current = f"{current}\n\n{block}" if current else block
    if current:
        chunks.append(Chunk(document.doc_id, len(chunks), current))
    return chunks
