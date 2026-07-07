# AI Email Assistant Harness

> **Branch:** `BANG-tools` | **Version:** 1.0.0

An agentic AI Email Assistant that reads Gmail threads, drafts intelligent replies,
enforces **mandatory human approval** before sending, and logs every action immutably.

Built as a Harness Engineering reference implementation demonstrating:
- Human-in-the-Loop (HITL) workflow orchestration
- Clean Architecture with strict layer boundaries
- Tool Layer with permission-safe agent access
- Append-only audit logging
- Graceful mock fallback for credentialless development

---

## Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure environment
```bash
cp .env.example .env
# Edit .env with your OpenAI API key and Gmail credentials
```

### 3. Run the demo (no credentials needed)
```bash
python -m src.cli email demo
```

### 4. Process a real Gmail thread
```bash
python -m src.cli email process <thread_id>
```

---

## CLI Commands

| Command | Description |
|---|---|
| `email process <thread_id>` | Fetch → Draft → Approval Gate → Send |
| `email demo` | Full workflow with mock Gmail data |
| `email review` | List drafts awaiting approval |
| `email approve <draft_id>` | Approve and send a draft |
| `email reject <draft_id>` | Reject a draft (not sent) |
| `email audit` | View recent audit log |
| `config` | Show current configuration |
| `version` | Show CLI version |

---

## Architecture

```
User → CLI → EmailWorkflowOrchestrator → Steps → Tool Layer → Gmail API
                                              ↓
                                        ApprovalGate ← Human Decision
                                              ↓
                                         AuditLogger
```

See [docs/architecture/architecture.md](docs/architecture/architecture.md) for full diagrams.

---

## Project Structure

```
src/
├── cli/              Typer CLI with Rich TUI
├── config/           pydantic-settings, constants, logging
├── models/           Domain entities (Email, Draft, ApprovalRecord, AuditEvent)
├── integrations/     Gmail OAuth, API client, MIME parser
├── tools/            Agent tool layer (BaseTool, ToolRegistry, 5 tools)
├── workflow/         State machine, orchestrator, 5 pipeline steps
├── approval/         asyncio.Future-based HITL gate
├── audit/            Append-only JSONL audit logger
└── infrastructure/   DB, Cache, Storage, Queue, LLM client/router
```

---

## Gmail Setup

See [docs/guides/gmail-setup.md](docs/guides/gmail-setup.md) for OAuth2 configuration.

---

## Reference Projects

> The `sample-projects/` folder contains **read-only** reference repositories.
> They are never modified — only studied for design patterns.

| Project | Key patterns adopted |
|---|---|
| `agents-from-scratch` | HITL interrupt, credential chain, tool pattern |
| `Email-AI-Agent` | LangGraph supervisor → pure Python state machine |
| `deliberate` | pydantic-settings, JSONL audit ledger, approval lifecycle |
| `agenticmail` | Tool registry/catalog pattern |
| `gmail-ai-draft` | OAuth2 + draft management |
