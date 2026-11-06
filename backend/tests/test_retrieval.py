from __future__ import annotations

from app.rag.bm25 import BM25Index, tokenize
from app.rag.chunking import Document, chunk_document


def test_tokenize_drops_stopwords_and_lowercases():
    assert tokenize("Why did we LOSE the Nordgrid deal?") == ["los", "nordgrid", "deal"]


def test_possessive_does_not_leave_a_stray_letter():
    assert tokenize("What is the CEO's salary?") == ["ceo", "salary"]


def test_stemmer_connects_word_forms():
    assert tokenize("lost") == tokenize("lose") == tokenize("losing")
    assert tokenize("sampled") == tokenize("sampling") == tokenize("sample")
    assert tokenize("won") == tokenize("win")
    assert tokenize("transformers") == tokenize("transformer")


def test_bm25_prefers_documents_with_rare_matching_terms():
    index = BM25Index(
        [
            "transformer oil sampling every twelve months",
            "gas insulated switchgear leak rate",
            "oil breakdown voltage limit",
        ]
    )
    results = index.search("transformer oil sampling")
    assert results[0][0] == 0
    assert all(score > 0 for _, score in results)


def test_bm25_returns_nothing_for_unknown_terms():
    index = BM25Index(["alpha beta", "gamma delta"])
    assert index.search("zzzz") == []
    assert index.search("") == []


def test_chunks_have_stable_citable_ids():
    doc = Document("doc-a", "Title", "# Title\n\nFirst paragraph.\n\nSecond paragraph.")
    chunks = chunk_document(doc, max_chars=40)
    assert [c.chunk_id for c in chunks] == [f"doc-a#{i}" for i in range(len(chunks))]
    assert len(chunks) >= 2


def test_heading_stays_with_following_paragraph():
    doc = Document("doc-b", "T", "# T\n\n## Section\n\nBody text here.")
    chunks = chunk_document(doc)
    assert "## Section\nBody text here." in chunks[0].text


def test_corpus_loads_all_documents(corpus):
    ids = set(corpus.documents)
    assert len(ids) == 16
    assert "wl-001-nordgrid" in ids
    assert "mm-statcom-cooling" in ids
    assert all(chunk.text.strip() for chunk in corpus.chunks)


def test_corpus_search_finds_the_right_document(corpus):
    top = corpus.search("Why did we lose the Nordgrid Utilities deal?", top_k=3)
    assert top[0].chunk.doc_id == "wl-001-nordgrid"

    top = corpus.search("How often should transformer oil be sampled?", top_k=3)
    assert top[0].chunk.doc_id == "mm-transformer-oil"

    top = corpus.search("What coolant conductivity is allowed for the STATCOM?", top_k=3)
    assert top[0].chunk.doc_id == "mm-statcom-cooling"
