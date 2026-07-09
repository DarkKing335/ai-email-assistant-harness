# GUI Gateway Contract

> **Owner:** Experience Layer (Ring 3 — Interface Adapters)
> **Audience:** Workflow, Approval, and Audit layer owners
> **Status:** Implemented in `src/gui/` — awaiting the Ring 2 fixes in §6
>
> The interface described here exists as `src/gui/gateway.py`, and the desktop
> app runs via `python -m src.gui`. Covered by 113 tests in `tests/unit/gui/`
> that run headless with no display, no Gmail account, and no LLM key —
> including a test that wires the *real* `ApprovalGate` to the real event-loop
> bridge and proves the workflow coroutine resumes on approve.

---

## 1. Purpose

`src/gui/gateway.py` is the **single seam** between the desktop GUI and the rest of
the system. It is the only module inside `src/gui/` permitted to import from
`src.workflow`, `src.approval`, `src.audit`, or `src.config.settings`.

Everything else in the GUI — views, widgets, viewmodels — talks only to this module.

This exists so that when `src/services/` is implemented, the GUI migrates from
calling `approval_gate.approve()` to calling `approval_service.approve()` by
editing **one file**, not every view.

### Rules this module enforces

| Rule | Reason |
|---|---|
| The GUI **never** imports `src.tools.*` | `GmailSendTool` carries `requires_approval=True` and is filtered out of `get_agent_tools()`. A GUI that can call it is an agent that can send mail. |
| The GUI **never** imports `src.integrations.*` | Ring 3 must not reach sideways into another adapter. The GUI renders domain models, never Gmail API JSON. |
| The GUI **never** constructs a `WorkflowStateMachine` or a step | Control flow belongs to the orchestrator. |
| Sending is **not** an operation this module exposes | The GUI approves. The orchestrator sends. There is no `gateway.send()`. |
| `src.config.constants` and `src.models` may be imported anywhere | They are pure enums and Ring 1 entities. Only `src.config.settings` is gateway-only, because it is the environment-facing one. |

These are not conventions. `tests/unit/gui/test_layering.py` parses every module
under `src/gui/` with `ast` and asserts the import graph, so the invariant cannot
decay into a code-review habit. It also asserts `Gateway` exposes no attribute
whose name contains `send`.

---

## 2. Types crossing the boundary

The gateway returns **Ring 1 domain models**, unmodified. Ring 3 depending on
Ring 1 is legal under the dependency rule; only infrastructure imports are
forbidden.

- `src.models.draft.Draft`
- `src.models.email.EmailThread`, `EmailMessage`
- `src.models.approval_record.ApprovalRecord`
- `src.models.audit_event.AuditEvent`
- `src.config.constants.WorkflowStatus`, `ApprovalDecision`, `AuditAction`

The `viewmodels/` package converts these into plain display dicts. Views never
see a domain model. The gateway never returns a `dict` where a model exists.

---

## 3. Interface

Canonical source: `src/gui/gateway.py`. Summarised here; read the module for the
full docstrings.

**Types** live in `src/gui/types.py`, kept separate so that `viewmodels/` can
import them without pulling in `pydantic-settings` or the audit singleton. The
consequence is that the entire viewmodel package tests headless with nothing
installed but pytest.

| Type | Notes |
|---|---|
| `WorkflowResult` | `workflow_id, draft, thread, approval, error, is_approved` |
| `PendingItem` | `draft` and `thread` are `None` until BLOCKER-2 / BLOCKER-3 |
| `ProgressEvent` | `timestamp, logger_name, message, level` |
| `ConfigSummary` | Carries `llm_api_key_last4`. The key never crosses the boundary. |
| `GuardrailState` | `PASSED` / `FAILED` / `NOT_EVALUATED` |
| `GmailMode` | `READY` / `MOCK` / `NEEDS_AUTH` |

**Commands**

```python
async def start_workflow(thread_id: str) -> WorkflowResult
def approve(draft_id: str, comments: str = "") -> bool
def reject(draft_id: str, reason: str = "") -> bool
```

`start_workflow` does **not** return when the draft is ready. `ApprovalStep`
awaits an `asyncio.Future` inside the gate, so the coroutine stays suspended
until a decision is made. Run it as a background task and discover the draft
through `list_pending()` — never through this return value.

`approve` and `reject` take **no `reviewer` parameter**, by design. Identity
comes from `src/gui/session.py`. `ApprovalRecord.reviewer` and `AuditEvent.actor`
are the accountability record; if any view could pass an arbitrary string, the
audit trail would be forgeable from the UI.

**Queries** — all safe to poll; the gate holds pending state in memory.

```python
def list_pending() -> list[PendingItem]
def pending_count() -> int
def recent_audit(limit: int = 50) -> list[AuditEvent]
def config_summary() -> ConfigSummary
def workflow_states() -> list[WorkflowStatus]          # iterate the enum, never hardcode
def workflow_history() -> list[WorkflowStatus] | None   # always None today: BLOCKER-1
```

**Observation**

```python
def subscribe_progress(cb: Callable[[ProgressEvent], None]) -> Callable[[], None]
```

Attaches a `logging.Handler` to the `email_assistant` logger, the same technique
as `cli/runner.py::_ProgressCapture`. Necessary because the orchestrator never
writes `ctx.status`, so log records are the only observable evidence of
progress. `emit` runs on whichever thread logged; the callback must marshal onto
the UI thread. Requires `configure_logging()` to have run, or INFO records are
dropped at the source.

**Lifecycle**

```python
def get_gateway() -> Gateway          # lazy: avoids import-time filesystem I/O
def bootstrap_session() -> Session    # seeds reviewer identity from settings
```

`bootstrap_session()` lives here rather than in `session.py` so that
`gateway.py` remains the single importer of `src.config.settings`.

`detect_gmail_mode()` predicts mock-vs-live **by inspection**, never by
constructing a `GmailClient`. `GmailClient.__init__` calls `get_credentials()`,
which falls through to `flow.run_local_server(port=8080)` (`auth.py:116`) and
opens a browser. A config panel must never trigger that.

---

## 4. Exact `WorkflowContext` fields the GUI reads

From the `WorkflowContext` returned by `EmailWorkflowOrchestrator.run()`:

| Field | Read? | Notes |
|---|---|---|
| `workflow_id` | ✅ | |
| `draft` | ✅ | `Draft \| None` |
| `email_thread` | ✅ | `EmailThread \| None`. Note: **`email_thread`**, not `thread` |
| `is_approved` | ✅ | Currently always `False` — see BLOCKER-4 |
| `metadata["error"]` | ✅ | The error string. **There is no `ctx.error` attribute.** |
| `metadata["approval_record"]` | ✅ | The `ApprovalRecord`. **There is no `ctx.approval` attribute.** |
| `status` | ❌ | Never written by the orchestrator — always `RECEIVED`. See BLOCKER-1 |
| `approval_record_id` | ❌ | Redundant; we read the record from `metadata` |
| `thread_id` | ❌ | We already hold it |
| `current_retry` / `max_retries` | ❌ | Internal to Ring 2 |

`src/cli/runner.py:92` reads `ctx.error` and `src/cli/runner.py:111` reads
`ctx.approval`. Both raise `AttributeError`. That code must not be copied.

---

## 5. What works today

Verified present and stable — the gateway can be built against these now:

- `ApprovalGate.list_pending() / approve() / reject() / pending_count`
- `AuditLogger.read_recent(limit) -> list[AuditEvent]`
- `settings` (all fields in `ConfigSummary` exist)
- All Ring 1 domain models
- The `WorkflowStatus` enum and `VALID_TRANSITIONS` table
- Live progress via a logging handler on `email_assistant`

---

## 6. What we need from Ring 2

Ordered by severity. The GUI can be built and demoed without 2 and 3; it
**cannot demonstrate the product's core promise** without 1 and 4.

### BLOCKER-1 — Workflow state is unobservable

`orchestrator.run()` creates `sm = WorkflowStateMachine(...)` as a **local
variable** and never writes back to `ctx.status`. The state history exists only
inside `run()`'s stack frame and is passed to `AuditStep`.

The GUI cannot render a state timeline — the flagship feature that makes the
harness legible.

**Ask:** either set `ctx.status = new_state` on every transition, or attach the
machine to the context (`ctx.state_machine = sm`) so `history()` is reachable.
The former is cleaner.

### BLOCKER-2 — The pending queue exposes no draft body

`ApprovalGate.list_pending()` returns `{draft_id, to, subject, preview,
requested_at, timeout_at}`. `preview` is `body[:200]`.

Because `run()` blocks inside the gate, the returned `ctx` is unavailable while a
draft awaits review. The queue is therefore the *only* source of draft data —
and it cannot supply the full body. **A reviewer cannot read the email they are
approving.**

**Ask:** add `ApprovalGate.get_pending(draft_id) -> tuple[ApprovalRecord, Draft] | None`.
The gate already holds the `Draft` in `self._pending`; it is simply not exposed.

### BLOCKER-3 — The original thread is unreachable from the queue

The gate stores `(ApprovalRecord, Draft, Future)`. It does not store the
`EmailThread`. The GUI cannot show the reviewer the message being replied to,
and cannot fetch it itself without importing `src.tools` — which this contract
forbids.

**Ask:** have `ApprovalStep` register the thread alongside the draft, or store
the `WorkflowContext` reference in the pending entry.

### BLOCKER-4 — `ctx.is_approved` is never set

`ApprovalStep.execute()` writes `ctx.approval_record_id` and
`ctx.metadata["approval_record"]`, but never `ctx.is_approved`.
`orchestrator.py:68` reads `if ctx.is_approved:` — so **every workflow takes the
`REJECTED → TERMINATED` branch, including ones a human explicitly approved.**
`SendStep` is unreachable code.

**Ask:** one line in `approval_step.py`:
`ctx.is_approved = decision_record.is_approved`

### BLOCKER-5 — The orchestrator cannot run at all

`orchestrator.run()` calls `.run()` on every step, but:

- `IngestStep`, `ApprovalStep`, `SendStep`, `AuditStep` define only `execute()`
  (per `BaseWorkflowStep`) → `AttributeError` at `orchestrator.py:48`
- `DraftStep` does not inherit `BaseWorkflowStep` and defines `run()` instead
- `DraftStep` reads `ctx.thread`; the field is `ctx.email_thread`
- `orchestrator.py:84` calls `self._audit.run(ctx, sm.history())` — two args;
  `AuditStep.execute(ctx)` takes one

**Ask:** settle on one method name across `BaseWorkflowStep` and all five steps.

> Why this was never caught: `tests/unit/test_orchestrator.py` assigns
> `orchestrator._ingest.run = mock_ingest_run` onto each step — *creating* the
> method that does not exist — and then never calls `orchestrator.run()`. It
> executes the mocks in sequence and reimplements the approval branch inline, so
> it asserts against its own fakes rather than against the orchestrator. It also
> sets `ctx.is_approved = True` by hand, which is what hides BLOCKER-4.

### BLOCKER-6 — Audit timestamps are regenerated on read

`AuditLogger.read_recent()` reconstructs each `AuditEvent` without passing
`timestamp=`, so the dataclass default (`datetime.utcnow`) fires and every event
carries the time the log was **read**, not the time it occurred. The persisted
JSONL line holds the correct value; it is discarded on load.

An audit log whose timestamps are regenerated on read is not an audit log.
`src/cli/app.py:220` already displays these wrong times today.

**Ask:** pass `timestamp=datetime.fromisoformat(data["timestamp"])` in
`logger.py:82`.

### BLOCKER-7 — The orchestrator does not build its own tool registry

`build_default_registry()` is called from exactly one place:
`src/cli/app.py:358`. `EmailWorkflowOrchestrator` never calls it, but
`SendStep` uses the `tool_registry` singleton and `EmailWritingAgent.__init__`
grabs it too. Launched from any entry point other than the CLI, the registry is
empty and both steps fail to find their tools.

The GUI **cannot** fix this on its side: calling `build_default_registry()`
requires importing `src.tools`, which is precisely the boundary that keeps
`GmailSendTool` out of the Experience Layer. `src/gui/__main__.py` deliberately
does not call it.

This is a Ring 2 concern that leaked into Ring 3. An orchestrator that depends
on a global being initialised by whoever happened to launch the process is not
self-contained.

**Ask:** call `build_default_registry()` from `EmailWorkflowOrchestrator.__init__`
(it is idempotent), or have each step resolve its own tools.

### NON-BLOCKING — Approval never times out

`ApprovalStep` computes `approval.timeout_at` from
`settings.approval_timeout_seconds`, but `ApprovalGate.wait_for_decision()`
awaits the future with no timeout. The GUI will render a countdown that never
fires. Cosmetic for us; flagging for the gate owner.

---

## 7. Known constraint: the gate is process-local

`approval_gate` is a module-level singleton holding `asyncio.Future` objects.
The workflow coroutine and the `approve()` call **must share one event loop in
one process.**

This is why the CLI's approval flow cannot work: `email process` and
`email approve` are separate processes with separate gate instances, and the
second one's `_pending` dict is always empty.

The GUI runs the orchestrator as a task on a loop it owns (`src/gui/bridge.py`),
so approve/reject resolve correctly. Consequences we accept:

- No separate worker process.
- **Pending drafts do not survive closing the window.** They are in-memory futures.

Both are acceptable for a desktop app. Neither should be papered over in the UI —
if the queue is empty after a restart, say so.

### And the gate is not thread-safe

`ApprovalGate.approve()` calls `future.set_result()` synchronously.
`asyncio.Future` is not thread-safe. Called from a thread other than the one
running the loop, `set_result()` schedules its callbacks through
`loop.call_soon()`, which in non-debug mode neither raises nor wakes the loop's
selector.

Verified: `approve()` **returns True**, the UI reports success, and the workflow
coroutine never resumes. A silent hang — the worst possible failure mode for an
approval gate.

This has never bitten the CLI, because `email approve` runs in a separate
process and never shares a loop with anything.

**Consequence for `bridge.py`:** the naive "run asyncio in a background thread
and click Approve from the Tk thread" design is wrong. Either

* drive the asyncio loop from the Tk main thread with a `root.after()` pump, so
  everything is single-threaded (recommended — no marshalling to get wrong), or
* keep the worker thread and route every `approve()` / `reject()` through
  `loop.call_soon_threadsafe` / `asyncio.run_coroutine_threadsafe`.

`Gateway.approve()` and `.reject()` document this affinity requirement.

**Ask (optional, defensive):** make `ApprovalGate.approve()` / `.reject()`
resolve their futures with `loop.call_soon_threadsafe(future.set_result, ...)`,
capturing the loop at `wait_for_decision()` time. That would make the gate
correct regardless of which thread the caller is on.

---

## 8. What the GUI promises not to do

Derived from `ADR-0001` and `harness-concepts.md`. These are invariants, not
preferences:

- **No send button.** No path from a click to `GmailSendTool`.
- **No auto-approve** in any form: no "trust this sender", no "remember my
  choice", no approve-on-timeout, no confidence threshold. ADR-0001 rejects all
  three by name.
- **No LLM confidence score shown as a decision aid.** It is uncalibrated.
- **No editable or deletable audit log.** Read-only, append-only.
- **No secrets rendered** — no OAuth token, refresh token, or client secret.
- **No `requires_approval` toggle.** It is an architectural invariant, not a
  setting.
- **No role selector** until `src/permissions/` enforces one. A dropdown that
  enforces nothing teaches users the system has access control when it does not.
- **Chain-of-thought is opt-in**, in a collapsed drawer, off by default.
