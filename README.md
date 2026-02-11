# Konex Pro — Intelligent Agentic Backend

> **Enterprise-Grade Persona Engine**: A deterministic, stateful agent backend designed for reliable business automation using **LangGraph** and **LiteLLM**.

**Konex Pro** is the core backend service for the Konex ecosystem. It provides the intelligence layer for conversational agents, handling state management, persona switching, and retrieval-augmented generation (RAG) with strict memory isolation.

---

## Core Philosophy

1.  **Strict State Management**: Rejects "black box" agent loops in favor of explicit, debuggable state machines.
2.  **Provider Agnostic**: Built on **LiteLLM** to support OpenAI, Anthropic, Gemini, or local models without code changes.
3.  **Memory Isolation**: distinct user sessions and persona contexts never leak.
4.  **IIAB Native**: Designed for deep integration with the Internet-in-a-Box (IIAB) ecosystem.

---

## Architecture

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Orchestration** | [LangGraph](https://langchain-ai.github.io/langgraph/) | Cyclic graph execution and state transitions. |
| **Inference** | [LiteLLM](https://docs.litellm.ai/) | Unified API for 100+ LLM providers. |
| **RAG** | FAISS + SentenceTransformers | Local, offline-capable semantic search. |
| **API** | FastAPI | High-performance async REST endpoints (`/v1/chat/completions`). |
| **Persistence** | SQLite / Postgres | Checkpointing for long-running sessions. |

---

## Directory Structure

- **`app/api`**: FastAPI routes and server configuration.
- **`app/graph`**: LangGraph nodes, edges, and agent logic.
- **`app/rag`**: Vector store, embedding, and data chunking pipelines.
- **`data`**: Storage for RAG sources and vector indices.

---

## Quick Start (Development)

This repository is designed to be "Upcycled" into a production deployment via Ansible, but can be run locally for development.

### 1. Setup
```bash
cp .env.example .env
# Edit .env with your API keys (OPENAI_API_KEY, RAPIDPRO_API_TOKEN, etc.)
```

### 2. Install Dependencies
```bash
pip install -e .
```

### 3. Run Server
```bash
uvicorn app.api.app:create_app --reload --port 8085
```

---

## Production Deployment

This codebase is deployed to `/opt/iiab/konex-backend` using the official Ansible role:

```yaml
# In /etc/iiab/local_vars.yml
konex_backend_install: True
```

The role handles:
- Creating the `konex` system user.
- Installing dependencies in a dedicated venv.
- Configuring Systemd (`konex-backend.service`).
- Setting up Nginx reverse proxy.

---

## Extending Konex

To add new capabilities:
1.  **Tools**: Add new tool functions in `app/graph/tools/`.
2.  **Personas**: Define new persona prompts in `app/graph/prompts.py`.
3.  **Knowledge**: Ingest new data into the `data/` directory and rebuild the index.

---

## License

Distributed under the MIT License.
