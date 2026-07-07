# ADR 0001 — Approval Gate Design

## Status

Accepted

## Date

2026-07-07

## Context

The AI Email Assistant uses an LLM to draft email replies on behalf of users. Email is a high-stakes communication channel. A mistake — such as sending a reply containing incorrect information, sensitive data, or an inappropriate tone — can have real consequences for business relationships, legal compliance, and user trust.

The initial design considered two options:

1. **Fully autonomous sending** — The agent sends emails without human review.
2. **Mandatory human approval gate** — Every draft must be explicitly approved before sending.

A third option, **probabilistic approval** (approve automatically if confidence score exceeds a threshold), was also considered.

---

## Decision

**Implement a mandatory, non-bypassable human approval gate.**

Every email draft produced by the agent must receive an explicit `APPROVED` decision from a human reviewer before the system is permitted to send it. The workflow state machine enforces this: there is no valid transition from `DRAFTED` to `SENDING` without a recorded `ApprovalRecord` with status `APPROVED`.

---

## Rationale

### Why not fully autonomous sending?

- LLMs hallucinate. A confident-sounding but factually incorrect reply sent to an external party is a reputational and legal risk.
- The system cannot know the user's full intent, relationship history, or political sensitivities from email content alone.
- Users need to trust the system before granting it full autonomy. A phased approach begins with full human review.

### Why not probabilistic approval?

- Confidence scores from LLMs are not calibrated and should not be used as a proxy for correctness.
- A threshold-based bypass creates a hidden attack surface: a prompt injection attack could produce a high-confidence malicious reply.
- Regulatory environments (GDPR, HIPAA, financial compliance) often require human sign-off on automated communications.

### Why mandatory approval?

- It is the safest default. Autonomy can be extended incrementally once the system has demonstrated reliable performance on a known corpus of requests.
- It teaches the agent what good looks like through the reviewer's decisions, enabling future fine-tuning or reinforcement learning from human feedback (RLHF).
- It provides a complete, auditable decision chain for every sent email.

---

## Implementation

The approval gate is implemented as a synchronous blocker in the workflow state machine:

```
RECEIVED → INGESTED → DRAFTED → [GUARDRAILS PASS] → AWAITING_APPROVAL
                                                              │
                                              ┌───────────────┴───────────────┐
                                              │                               │
                                        APPROVED                          REJECTED
                                              │                               │
                                          SENDING                        TERMINATED
                                              │
                                           SENT → AUDITED
```

Key implementation files:
- `src/approval/gate.py` — The blocking gate that checks for a valid `ApprovalRecord`.
- `src/approval/notifier.py` — Sends the draft to the reviewer via CLI output, email, or webhook.
- `src/workflow/engine/state_machine.py` — The state machine that enforces valid transitions.
- `src/workflow/steps/approval_step.py` — The workflow step that invokes the gate.

---

## Consequences

### Positive

- Maximum safety: no email is ever sent without human intent.
- Full auditability: every approval decision is recorded with actor, timestamp, and rationale.
- Trust building: users gain confidence in the system before considering autonomous modes.
- Compliance-ready: meets requirements for human oversight in regulated industries.

### Negative

- Latency: the workflow cannot complete without a human action. For high-volume inboxes, this creates a review queue bottleneck.
- Reviewer fatigue: if the agent produces low-quality drafts, reviewers must reject frequently, reducing the system's utility.
- Not suitable for real-time email response SLAs.

### Mitigations

- The `reflection.py` self-critique step in the agent reduces draft rejection rates by catching obvious errors before the gate.
- The guardrails layer further reduces reviewer cognitive load by ensuring the draft is clean when it reaches them.
- Future ADRs may introduce a supervised autonomy tier for low-risk email categories (e.g., acknowledgment replies) once the system's accuracy is validated.

---

## Alternatives Rejected

| Option | Reason Rejected |
|---|---|
| Fully autonomous sending | Too high a risk of harmful, incorrect, or inappropriate emails being sent |
| Confidence-threshold bypass | LLM confidence scores are unreliable and create a security bypass surface |
| Time-based auto-approval | Fails in asynchronous environments and violates the principle of explicit human intent |
