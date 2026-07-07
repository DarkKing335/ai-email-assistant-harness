# Harness Engineering Concepts

## Overview

This project is a reference implementation demonstrating key **Harness Engineering** concepts applied to a real-world AI agentic system. The term "Harness" refers to the control infrastructure that wraps around an autonomous AI agent to make it safe, observable, auditable, and governable in production.

---

## Core Harness Concepts Demonstrated

### 1. Workflow Orchestration

**What it is:** A harness defines the sequence of steps an agent must follow. The agent does not decide its own execution path.

**Where it appears in this project:**
- `src/workflow/engine/orchestrator.py` — Drives all steps in a fixed sequence.
- `src/workflow/engine/state_machine.py` — Enforces valid state transitions. The agent cannot skip the approval step.
- `src/workflow/steps/` — Each step is an isolated, testable unit of work.

**Why it matters:** Without orchestration, an LLM-backed agent can hallucinate its own workflow, skip critical steps, or loop indefinitely. The harness owns the control flow.

---

### 2. Human-in-the-Loop (HITL) Approval Gate

**What it is:** A mandatory checkpoint that pauses autonomous execution and requires an explicit human decision before proceeding.

**Where it appears in this project:**
- `src/approval/gate.py` — The hard-blocking gate. The workflow cannot transition from `DRAFTED` to `SENDING` without a recorded approval.
- `src/workflow/steps/approval_step.py` — The workflow step that invokes the gate and waits.
- `src/approval/notifier.py` — Alerts the human reviewer that action is required.

**Why it matters:** This is the single most important safety mechanism. No email is ever sent by the AI alone. Human judgment is required for every outbound message.

---

### 3. Permission Engine

**What it is:** A role-based access control (RBAC) system that determines what each actor is allowed to do before any action is executed.

**Where it appears in this project:**
- `src/permissions/engine.py` — Evaluates a (subject, action, resource) triple against loaded policies.
- `src/permissions/policy.py` — Declarative policy definitions.
- `src/permissions/role.py` — Role definitions: `operator`, `reviewer`, `admin`.

**Why it matters:** Prevents privilege escalation. An `operator` role can draft but not approve. A `reviewer` can approve but not configure system policies.

---

### 4. Guardrails

**What it is:** Automated checks that intercept and validate agent outputs before they reach the human reviewer or the send step.

**Where it appears in this project:**
- `src/guardrails/content_filter.py` — Blocks drafts with prohibited content.
- `src/guardrails/pii_detector.py` — Detects and redacts PII before the draft is shown to a reviewer.
- `src/guardrails/rate_limiter.py` — Prevents runaway LLM usage.
- `src/guardrails/output_validator.py` — Ensures the draft meets format, length, and structural requirements.

**Why it matters:** Guardrails are the automated safety net that catches issues the human reviewer should not have to handle manually. They enforce non-negotiable system-level constraints.

---

### 5. Audit Logging

**What it is:** A structured, append-only log of every action, decision, and state transition in the system.

**Where it appears in this project:**
- `src/audit/logger.py` — Records events with actor, timestamp, action, resource, and outcome.
- `src/audit/event.py` — The structured event schema.
- `src/audit/reporter.py` — Generates compliance-ready audit reports.
- `src/workflow/steps/audit_step.py` — Ensures every pipeline run ends with an audit record.

**Why it matters:** Required for compliance, debugging, and post-incident analysis. Every email sent through the system must have a traceable chain of decisions.

---

### 6. Tool Layer Encapsulation

**What it is:** The agent interacts with external systems only through a controlled, registered set of tools — never through direct SDK calls in agent code.

**Where it appears in this project:**
- `src/tools/base_tool.py` — Defines the tool interface contract.
- `src/tools/gmail_reader_tool.py`, `gmail_draft_tool.py`, `gmail_send_tool.py` — Concrete tool implementations.
- `src/agents/email_writing_agent/executor.py` — Invokes only registered tools.

**Why it matters:** Tool encapsulation means the harness can log, throttle, mock, or disable any tool without touching agent logic. It is the foundation of agent observability.

---

### 7. Prompt Management

**What it is:** Centralized, versioned management of all prompts sent to the LLM. No prompt strings are hardcoded in agent business logic.

**Where it appears in this project:**
- `src/prompts/templates/` — Jinja2 prompt templates with named variables.
- `src/prompts/manager.py` — Renders templates with runtime variables and tracks prompt versions.
- `src/prompts/registry.py` — Maps logical prompt names to template files.

**Why it matters:** Separating prompts from code allows prompt engineers to iterate without code changes, and enables A/B testing and rollback of prompts independently of application logic.

---

### 8. Memory Architecture

**What it is:** A two-tier memory system that gives the agent access to recent context (short-term) and relevant historical interactions (long-term).

**Where it appears in this project:**
- `src/memory/short_term/context_window.py` — Manages the in-session LLM context.
- `src/memory/long_term/memory_store.py` — Persists past drafts, approval decisions, and contact history.
- `src/memory/long_term/memory_retriever.py` — Retrieves semantically relevant memories to inject into prompts.

**Why it matters:** Without memory management, the agent has no continuity. With it, the agent can maintain appropriate tone and context across multiple email threads with the same contact.

---

## Harness vs. Pure Agent

| Concern | Pure Agent | Harness-Wrapped Agent |
|---|---|---|
| Execution flow | Agent decides | Harness orchestrates |
| Sending emails | Agent sends freely | Requires human approval |
| Tool access | Unrestricted | Registered tools only |
| Audit trail | None | Every action logged |
| Permission control | None | RBAC enforced |
| Output safety | None | Guardrails applied |
| Prompt changes | Code changes | Template updates |
