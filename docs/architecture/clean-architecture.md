# Clean Architecture in the AI Email Assistant Harness

## What Is Clean Architecture?

Clean Architecture (Robert C. Martin, 2017) organizes code into concentric dependency rings where **inner rings never depend on outer rings**. This enforces separation of concerns, makes the domain logic independently testable, and keeps infrastructure details (databases, APIs, LLM providers) swappable without touching business rules.

---

## The Four Rings Applied to This Project

```
┌───────────────────────────────────────────────────┐
│                  Infrastructure                   │  ← Outermost: changes freely
│  (database, Gmail API, Redis, LLM SDK, FastAPI)   │
│  ┌─────────────────────────────────────────────┐  │
│  │              Interface Adapters             │  │
│  │  (API routers, CLI commands, schemas,       │  │
│  │   Gmail client, tool implementations)      │  │
│  │  ┌───────────────────────────────────────┐ │  │
│  │  │          Application / Use Cases      │ │  │
│  │  │  (services, workflow steps, approval  │ │  │
│  │  │   gate, permission engine, guardrails,│ │  │
│  │  │   audit logger, agent executor)       │ │  │
│  │  │  ┌─────────────────────────────────┐ │ │  │
│  │  │  │       Domain / Entities         │ │ │  │
│  │  │  │  (models: Email, Draft,         │ │ │  │
│  │  │  │   ApprovalRecord, AuditEvent,   │ │ │  │
│  │  │  │   User, Policy, Role)           │ │ │  │
│  │  │  └─────────────────────────────────┘ │ │  │
│  │  └───────────────────────────────────────┘ │  │
│  └─────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────┘
```

---

## Ring Responsibilities

### Ring 1 — Domain Entities (`src/models/`)

The innermost ring. Contains pure Python data classes representing the core business objects. **No imports from any other project layer.**

| File | Entity |
|---|---|
| `email.py` | A parsed, normalized incoming email message |
| `draft.py` | An agent-generated email reply draft |
| `approval_record.py` | The full lifecycle record of a human approval decision |
| `audit_event.py` | A single immutable, timestamped audit log entry |
| `user.py` | An authenticated system user with a role |

---

### Ring 2 — Application / Use Cases

Contains all business logic. Depends **only on Ring 1**. Never imports from `src/api/`, `src/integrations/`, or `src/infrastructure/`.

| Directory | Role |
|---|---|
| `src/services/` | Use-case orchestrators (email service, draft service, approval service) |
| `src/workflow/` | State machine and workflow step handlers |
| `src/approval/` | Approval gate logic and notifier interface |
| `src/permissions/` | Permission engine and policy evaluator |
| `src/guardrails/` | Content filter, PII detector, output validator, rate limiter |
| `src/audit/` | Audit logger and reporter |
| `src/agents/` | Agent planner, executor, and reflection logic |
| `src/prompts/` | Prompt manager and template registry |
| `src/memory/` | Short-term and long-term memory abstractions |

---

### Ring 3 — Interface Adapters

Translates between the application layer and the outside world. Depends on Ring 1 and Ring 2.

| Directory | Role |
|---|---|
| `src/api/routers/` | FastAPI routers that map HTTP requests to service calls |
| `src/api/schemas/` | Pydantic models for request/response serialization |
| `src/api/middleware/` | Auth and logging middleware |
| `src/cli/commands/` | Typer CLI commands that call service methods |
| `src/tools/` | Agent tool implementations that wrap Gmail client calls |
| `src/integrations/gmail/` | Concrete Gmail API client, parser, and sender |

---

### Ring 4 — Infrastructure

The outermost ring. Contains all third-party SDK usage, database sessions, cache connections, and task queue bindings. Depends on all inner rings via dependency injection.

| Directory | Role |
|---|---|
| `src/infrastructure/database/` | Connection pool and migration runner |
| `src/infrastructure/storage/` | File store and object store implementations |
| `src/infrastructure/cache/` | Redis-backed cache client |
| `src/infrastructure/queue/` | Celery task queue bindings |
| `src/infrastructure/llm/` | LLM provider client and routing logic |

---

## The Dependency Rule in Practice

```
# CORRECT — Application layer calls an abstract interface
class DraftService:
    def __init__(self, draft_repo: AbstractDraftRepository):
        self._repo = draft_repo

# WRONG — Application layer imports a concrete infrastructure class
from src.infrastructure.database.connection import SessionLocal  # ← NEVER do this in a service
```

All concrete infrastructure implementations are injected at the composition root (`src/cli/main.py` or the FastAPI app factory) via constructor injection.

---

## Testability Benefit

Because the domain and application layers have no infrastructure dependencies, every use case can be unit-tested with in-memory fakes and mocks — no database, no Gmail API, no LLM calls required.

```
tests/unit/
├── agents/          # Test agent logic with a fake LLM client
├── approval/        # Test gate logic with a fake notifier
├── guardrails/      # Test filters with sample text inputs
├── permissions/     # Test policy evaluation with inline rules
└── workflow/        # Test state transitions with a fake step registry
```
