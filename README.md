# Agent Lab

A small lab for building, versioning and testing RAG agents:

- **Agent registry** with immutable versions (model, prompt, settings) and run history
- **RAG demo agent** that answers from documents with citations, uses a SQL tool for structured questions, and rejects answers that are not grounded in its sources
- **Evaluation harness** with repeatable runs, regression comparison and a CI gate
- **Local LLM benchmark** for Ollama and other OpenAI compatible servers (latency, tokens per second, quality)
- Works **fully offline** with a built-in mock provider, so tests and demos need no API key

Status: work in progress. This README is expanded as the features land.
