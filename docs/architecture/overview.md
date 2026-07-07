# System Architecture Overview

## Purpose

The AI Email Assistant Harness is an agentic system that reads incoming emails, drafts intelligent replies using a Large Language Model (LLM), enforces a mandatory human approval gate before sending, and integrates natively with Gmail. The project also serves as a reference implementation demonstrating Harness Engineering concepts such as workflow orchestration, guardrails, permission engines, and audit logging.

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Entry Points                             │
│                                                                 │
│   ┌─────────────┐   ┌─────────────────┐   ┌─────────────────┐  │
│   │   CLI       │   │   REST API      │   │  Webhook / Poll │  │
│   └──────┬──────┘   └────────┬────────┘   └────────┬────────┘  │
└──────────┼───────────────────┼─────────────────────┼───────────┘
           │                   │                     │
           └───────────────────▼─────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │   Workflow Engine   │
                    │  (Orchestrator /   │
                    │   State Machine)   │
                    └──────────┬──────────┘
                               │
          ┌────────────────────┼────────────────────┐
          │                    │                    │
   ┌──────▼──────┐    ┌────────▼────────┐   ┌──────▼──────┐
   │   Ingest    │    │  Email Writing  │   │  Approval   │
   │    Step     │    │     Agent       │   │    Gate     │
   └─────────────┘    └────────┬────────┘   └──────┬──────┘
                               │                    │
                    ┌──────────▼──────────┐          │
                    │     Tool Layer      │          │
                    │ (Gmail Reader,      │          │
                    │  Summarizer, ...)   │          │
                    └──────────┬──────────┘          │
                               │                     │
                    ┌──────────▼──────────┐          │
                    │  Gmail Integration  │◄─────────┘
                    │   (Send / Draft)    │
                    └──────────┬──────────┘
                               │
          ┌────────────────────┼────────────────────┐
          │                    │                    │
   ┌──────▼──────┐    ┌────────▼────────┐   ┌──────▼──────┐
   │ Permissions │    │   Guardrails    │   │Audit Logger │
   │   Engine    │    │ (PII, Filter,   │   │             │
   └─────────────┘    │  Validator)     │   └─────────────┘
                      └─────────────────┘

                    ┌─────────────────────┐
                    │    Infrastructure   │
                    │ (DB, Cache, Queue,  │
                    │   LLM, Storage)     │
                    └─────────────────────┘
```

---

## Core Components

| Component | Responsibility |
|---|---|
| **CLI** | Human-facing command-line interface for running, reviewing, and approving emails |
| **REST API** | Programmatic interface for external systems and webhooks |
| **Workflow Engine** | Orchestrates the full pipeline via a state machine |
| **Email Writing Agent** | LLM-backed agent that plans, drafts, and reflects on email replies |
| **Approval Gate** | Hard stop that requires an explicit human decision before sending |
| **Permission Engine** | Enforces role-based access control over all system actions |
| **Guardrails** | Content filtering, PII redaction, output validation, and rate limiting |
| **Tool Layer** | Pluggable tools the agent uses to interact with Gmail and other services |
| **Gmail Integration** | OAuth2-authenticated Gmail API client for reading, drafting, and sending |
| **Memory** | Short-term context window and long-term interaction memory |
| **Prompt Management** | Versioned Jinja2 prompt templates with a central registry |
| **Audit Logging** | Tamper-evident, timestamped log of every action in the system |
| **Infrastructure** | Database, cache, task queue, object storage, and LLM client abstractions |

---

## Data Flow

1. **Trigger** — A new email arrives via Gmail push notification or polling.
2. **Ingest** — The email is fetched, parsed, and stored as a domain model.
3. **Draft** — The Email Writing Agent reads the thread, plans a reply, drafts it, and self-reflects.
4. **Guardrails** — The draft passes through content filtering, PII detection, and output validation.
5. **Approval Gate** — The draft is presented to a human reviewer. The workflow pauses.
6. **Decision** — The reviewer approves or rejects. If rejected, the workflow can re-draft or terminate.
7. **Send** — The approved draft is submitted to Gmail and delivered.
8. **Audit** — Every step, decision, and outcome is recorded in the immutable audit log.

---

## Key Design Decisions

- **Clean Architecture** is enforced: domain models are independent of infrastructure. See [`clean-architecture.md`](./clean-architecture.md).
- **Human approval is non-bypassable**: the `ApprovalGate` is a synchronous blocker in the state machine.
- **Guardrails are pre-send only**: they run after drafting but before the approval gate, so the human sees a clean, already-validated draft.
- **All LLM calls are routed through `llm_router.py`**: this allows model swapping without touching agent code.
- **The tool layer is pluggable**: new tools can be registered without modifying the agent core.

---

## Technology Assumptions

| Concern | Technology |
|---|---|
| LLM Provider | OpenAI GPT-4o / Google Gemini (swappable via `llm_router`) |
| Email Provider | Gmail (Google Workspace) |
| Auth | OAuth 2.0 (Gmail), Bearer tokens (REST API) |
| Database | PostgreSQL (primary), SQLite (local dev) |
| Cache | Redis |
| Task Queue | Celery + Redis |
| Object Storage | Google Cloud Storage / local filesystem |
| Prompt Templating | Jinja2 |
| API Framework | FastAPI |
| CLI Framework | Typer |
