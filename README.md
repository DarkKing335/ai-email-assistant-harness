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

### 2. Launch the desktop app — no credentials needed
```bash
python -m src.gui
```

Gmail and the LLM both fall back to mock data when their libraries or keys are
absent, so the app runs offline. The **Config** tab shows exactly which mode you
are in.

### 3. (Optional) Configure real credentials
```bash
cp .env.example .env          # then set OPENAI_API_KEY
python tools/generate_token.py    # one-time Gmail OAuth
```

---

## Desktop GUI

```bash
python -m src.gui
```

Tkinter ships with Python, so there is no extra GUI dependency.

| Tab | What it shows |
|---|---|
| **Dashboard** | Enter a thread ID, start a workflow, watch live progress |
| **Approvals** | Drafts awaiting your decision. Approve or reject with a comment |
| **Audit** | The append-only audit log. Read-only — no edit, no delete |
| **Config** | Environment, model, Gmail mode, reviewer. Never renders a secret |

**The GUI is the only interface that can complete the approval loop.** The
`ApprovalGate` holds pending decisions as in-memory `asyncio.Future` objects, so
the workflow and the approving click must share one process and one event loop.
`src/gui/bridge.py` pumps the asyncio loop from Tk's timer to guarantee that.

There is deliberately **no Send button**. The reviewer approves; the orchestrator
sends. `src/gui/` never imports `src.tools`, and
`tests/unit/gui/test_layering.py` fails the build if it ever does.

> **Authorise Gmail before a demo, not during one.** Without a saved token, the
> OAuth browser flow fires inside `IngestStep` on the UI thread and freezes the
> window. `python tools/generate_token.py` writes the token up front;
> `--check` reports status without prompting.

---

## Known limitations

The workflow layer has defects that block end-to-end execution. They are written
up with file and line numbers in
[docs/architecture/gui-gateway-contract.md](docs/architecture/gui-gateway-contract.md) §6.

- `orchestrator.run()` calls `step.run()`, but the steps define `execute()`.
  Both `python -m src.cli email demo` and the GUI's **Start workflow** button
  currently fail with `AttributeError: 'IngestStep' object has no attribute 'run'`.
- Nothing sets `ctx.is_approved`, so an approved draft still routes to
  `TERMINATED` and is never sent.
- The tool registry is only populated by `src/cli/app.py`, not by the orchestrator.
- **The CLI approval flow cannot work**: `email process` and `email approve` are
  separate processes, each with its own in-memory gate, so the second one's
  pending queue is always empty.

Where data is unavailable, the GUI states the reason rather than rendering an
empty panel.

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

> `email review` / `approve` / `reject` cannot resolve a draft created by
> `email process` — see **Known limitations** above. Use the GUI for the
> approval loop.

---

## Architecture

```
User → GUI / CLI → EmailWorkflowOrchestrator → Steps → Tool Layer → Gmail API
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
├── gui/              Desktop Experience Layer (Tkinter)
│   ├── gateway.py      The only module that talks to Ring 2
│   ├── bridge.py       asyncio loop pumped from Tk's timer
│   ├── session.py      Reviewer identity — the audit trail's source of truth
│   ├── viewmodels/     Pure domain → dict, tested headless
│   └── views/          Dashboard, Approvals, Audit, Config
├── cli/              Typer CLI with Rich TUI
├── config/           pydantic-settings, constants, logging
├── models/           Domain entities (Email, Draft, ApprovalRecord, AuditEvent)
├── integrations/     Gmail OAuth, API client, MIME parser
├── tools/            Agent tool layer (BaseTool, ToolRegistry, 5 tools)
├── workflow/         State machine, orchestrator, 5 pipeline steps
├── approval/         asyncio.Future-based HITL gate
├── audit/            Append-only JSONL audit logger
└── infrastructure/   DB, Cache, Storage, Queue, LLM client/router

tools/
└── generate_token.py   One-time Gmail OAuth authorisation
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
