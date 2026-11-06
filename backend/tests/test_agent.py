from __future__ import annotations

import json

from app.agents.prompts import REFUSAL_TEXT, REJECTED_TEXT
from app.agents.rag_agent import AgentConfig, RagAgent
from app.config import Settings
from app.providers import ChatMessage, ChatResult, ProviderError
from app.rag.citations import extract_citations, is_refusal, validate_answer


class ScriptedProvider:
    """Returns prepared replies in order, to test the control flow of the agent."""

    name = "scripted"

    def __init__(self, replies: list[str]) -> None:
        self.replies = list(replies)
        self.prompts: list[str] = []

    def chat(self, model: str, messages: list[ChatMessage], **kwargs) -> ChatResult:
        self.prompts.append(messages[-1].content)
        if not self.replies:
            raise ProviderError("no more scripted replies")
        return ChatResult(text=self.replies.pop(0), prompt_tokens=10, completion_tokens=5)

    def list_models(self) -> list[str]:
        return []

    def is_available(self) -> bool:
        return True


def make_agent(toolbox, **overrides) -> RagAgent:
    return RagAgent(AgentConfig(**overrides), toolbox, Settings())


# ------------------------------------------------------------------ citations


def test_extract_citations_keeps_order_and_removes_duplicates():
    text = "A [wl-001-nordgrid#0] and B [wl-002-baltic#1] and again [wl-001-nordgrid#0]."
    assert extract_citations(text) == ["wl-001-nordgrid#0", "wl-002-baltic#1"]


def test_validate_answer_rules():
    chunks = {"a#0", "a#1"}
    docs = {"a"}
    assert validate_answer("Fact [a#0].", chunks, docs).valid
    assert validate_answer("Fact [a].", chunks, docs).valid
    assert not validate_answer("Fact without source.", chunks, docs).valid
    assert not validate_answer("Fact [b#0].", chunks, docs).valid
    assert not validate_answer("Fact [a#9].", chunks, docs).valid
    assert not validate_answer("   ", chunks, docs).valid
    assert validate_answer(REFUSAL_TEXT, chunks, docs).valid
    assert validate_answer("Fact without source.", chunks, docs, require_citations=False).valid


def test_is_refusal():
    assert is_refusal(REFUSAL_TEXT)
    assert is_refusal("I could not find any information about that.")
    assert not is_refusal("We lost the deal because of price.")


# ----------------------------------------------------------- agent with the mock model


def test_agent_answers_document_question_with_citations(toolbox):
    result = make_agent(toolbox).run("Why did we lose the Nordgrid Utilities deal?")
    assert result.status == "answered"
    assert "VoltEdge" in result.answer
    assert any(c.startswith("wl-001-nordgrid") for c in result.citations)
    assert result.tools_used == ["search_documents"]
    assert result.llm_calls == 1
    assert result.latency_ms > 0


def test_agent_uses_records_tool_for_counts(toolbox):
    result = make_agent(toolbox).run("How many deals did we lose?")
    assert result.status == "answered"
    assert result.tools_used == ["query_records"]
    assert "6" in result.answer
    assert len(result.citations) == 6


def test_agent_records_tool_filters_by_competitor_and_outcome(toolbox):
    result = make_agent(toolbox).run("How many deals did we win against Altrix?")
    assert result.tools_used == ["query_records"]
    assert "3" in result.answer


def test_agent_refuses_when_nothing_is_retrieved(toolbox):
    result = make_agent(toolbox).run("What is the CEO salary?")
    assert result.status == "refused"
    assert result.answer == REFUSAL_TEXT
    assert result.llm_calls == 0


def test_agent_refuses_unknown_customer(toolbox):
    result = make_agent(toolbox).run("Did we win the deal with Tokyo Metropolitan Grid?")
    assert result.status == "refused"


def test_agent_reports_when_no_records_match(toolbox):
    result = make_agent(toolbox).run("How many deals did we win in Asia Pacific?")
    assert result.tools_used == ["query_records"]
    assert result.status == "answered"
    assert result.answer == "No matching deals were found in the records."
    assert result.llm_calls == 0


# ------------------------------------------------- validation, retry and rejection flow


def test_uncited_answer_is_retried_once_and_then_accepted(toolbox):
    agent = make_agent(toolbox)
    agent.provider = ScriptedProvider(
        ["VoltEdge was cheaper.", "VoltEdge was cheaper [wl-001-nordgrid#0]."]
    )
    result = agent.run("Why did we lose the Nordgrid Utilities deal?")
    assert result.status == "answered"
    assert result.llm_calls == 2
    assert [c["type"] for c in result.tool_calls] == ["route", "tool", "retry"]
    assert "rejected" in agent.provider.prompts[1]


def test_answer_is_rejected_when_it_stays_ungrounded(toolbox):
    agent = make_agent(toolbox, max_retries=1)
    agent.provider = ScriptedProvider(["No source here.", "Still no source."])
    result = agent.run("Why did we lose the Nordgrid Utilities deal?")
    assert result.status == "rejected"
    assert result.answer == REJECTED_TEXT
    assert result.raw_answer == "Still no source."
    assert result.validation_errors


def test_citation_to_unretrieved_source_is_rejected(toolbox):
    agent = make_agent(toolbox, max_retries=0)
    agent.provider = ScriptedProvider(["It was price [mm-protection-relays#0]."])
    result = agent.run("Why did we lose the Nordgrid Utilities deal?")
    assert result.status == "rejected"
    assert "not one of the provided sources" in result.validation_errors[0]


def test_provider_failure_becomes_error_status(toolbox):
    agent = make_agent(toolbox)
    agent.provider = ScriptedProvider([])
    result = agent.run("Why did we lose the Nordgrid Utilities deal?")
    assert result.status == "error"
    assert "no more scripted replies" in (result.error or "")


# -------------------------------------------------------------------------- llm router


def test_llm_router_is_used_when_it_returns_valid_json(toolbox):
    route = json.dumps({"tool": "query_records", "args": {"aggregate": "count", "outcome": "won"}})
    agent = make_agent(toolbox, router="llm")
    agent.provider = ScriptedProvider([route, "There are 6 deals [wl-002-baltic]."])
    result = agent.run("Tell me about our results")
    assert result.tool_calls[0]["source"] == "llm"
    assert result.tools_used == ["query_records"]
    assert result.status == "answered"


def test_llm_router_falls_back_to_heuristic_on_bad_json(toolbox):
    agent = make_agent(toolbox, router="llm")
    agent.provider = ScriptedProvider(
        ["not json at all", "VoltEdge was cheaper [wl-001-nordgrid#0]."]
    )
    result = agent.run("Why did we lose the Nordgrid Utilities deal?")
    assert result.tool_calls[0]["source"] == "heuristic_fallback"
    assert result.tools_used == ["search_documents"]
