# Harness Pipeline Integration Guide

## Overview

This guide explains how to integrate the AI Email Assistant Harness with a **Harness CI/CD platform** to automate testing, deployment, approval workflows, and operational monitoring using Harness Pipelines, Harness Approval Steps, and Harness STO (Security Testing Orchestration).

---

## Integration Architecture

```
┌──────────────────────────────────────────────────────┐
│                   Harness Platform                   │
│                                                      │
│  ┌─────────────┐   ┌──────────────┐   ┌───────────┐ │
│  │   Pipeline  │   │   Approval   │   │    STO    │ │
│  │   (CI/CD)   │──▶│    Stage     │──▶│  (Scans)  │ │
│  └─────────────┘   └──────────────┘   └───────────┘ │
│         │                                            │
└─────────┼────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────┐
│           AI Email Assistant Application            │
│                                                     │
│  ┌────────────┐   ┌───────────────┐   ┌──────────┐  │
│  │  Workflow  │   │ Approval Gate │   │  Audit   │  │
│  │   Engine   │──▶│  (HITL Stop)  │──▶│  Logger  │  │
│  └────────────┘   └───────────────┘   └──────────┘  │
└─────────────────────────────────────────────────────┘
```

---

## Part 1 — CI Pipeline (Build and Test)

### Pipeline Stages

#### Stage 1: Lint and Static Analysis

Runs code quality checks on every pull request and commit:

```yaml
# .harness/pipelines/ci.yaml (reference structure — not executable here)
stage:
  name: Lint
  steps:
    - run: ruff check src/ tests/
    - run: mypy src/ --strict
    - run: bandit -r src/ -ll
```

#### Stage 2: Unit Tests

Runs all unit tests with coverage enforcement:

```bash
pytest tests/unit/ --cov=src --cov-report=xml --cov-fail-under=80
```

#### Stage 3: Integration Tests

Runs integration tests against a sandboxed Gmail account and a local database:

```bash
pytest tests/integration/ -m "not live_gmail" --timeout=60
```

#### Stage 4: Security Scan (Harness STO)

Uses Harness STO to run SAST, dependency vulnerability scans, and secret detection:

- **SAST:** Semgrep rules for Python AI agent patterns.
- **Dependency scan:** Safety / pip-audit for known CVEs in `requirements.txt`.
- **Secret detection:** Gitleaks to prevent credential leakage.

---

## Part 2 — CD Pipeline (Deploy)

### Environment Promotion Strategy

```
feature branch → dev environment → staging environment → [Harness Approval] → production
```

### Stage: Deploy to Staging

```bash
# Environment variables are injected by Harness secrets manager
export DATABASE_URL=<harness-secret://staging/database-url>
export OPENAI_API_KEY=<harness-secret://shared/openai-api-key>
export GMAIL_TOKEN_PATH=<harness-secret://staging/gmail-token-path>

# Run migrations
alembic upgrade head

# Start application
uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

### Stage: Harness Manual Approval Gate (Pre-Production)

Before deploying to production, a Harness Approval Step is inserted in the pipeline:

| Setting | Value |
|---|---|
| **Approvers** | `platform-team` user group |
| **Minimum approvals** | 1 |
| **Approval timeout** | 4 hours |
| **Auto-reject on timeout** | Yes |

This mirrors the **human-in-the-loop approval gate** concept implemented in the application itself.

### Stage: Deploy to Production

Executes only after the Harness Approval step is satisfied. Uses a blue-green or canary deployment strategy.

---

## Part 3 — Connecting the Application Approval Gate to Harness

The application's approval gate (`src/approval/gate.py`) can be extended to publish approval requests directly to a Harness pipeline or webhook:

### Harness Webhook Trigger

Configure a Harness Custom Webhook trigger that the application calls when a draft is awaiting approval:

```
POST https://app.harness.io/gateway/pipeline/api/webhook/custom/<token>
Content-Type: application/json

{
  "draft_id": "<DRAFT_ID>",
  "subject": "Re: Project Proposal",
  "requester": "email-assistant-agent",
  "preview_url": "https://your-app.com/drafts/<DRAFT_ID>"
}
```

The Harness pipeline can then:
1. Notify reviewers via Slack, email, or PagerDuty.
2. Present the draft for review in a Harness Approval stage.
3. Call back to the application's REST API with the decision.

### Application Approval Callback Endpoint

```
POST /api/approvals/{draft_id}/decision
Authorization: Bearer <HARNESS_CALLBACK_TOKEN>

{
  "decision": "APPROVED",
  "reviewer": "john.doe@company.com",
  "comments": "Looks good, send it."
}
```

---

## Part 4 — Secrets Management

All sensitive credentials are stored in the Harness Secrets Manager and injected as environment variables at pipeline runtime:

| Secret Name | Used By |
|---|---|
| `gmail-client-id` | `src/integrations/gmail/auth.py` |
| `gmail-client-secret` | `src/integrations/gmail/auth.py` |
| `gmail-token-json` | `src/integrations/gmail/auth.py` |
| `openai-api-key` | `src/infrastructure/llm/llm_client.py` |
| `database-url` | `src/infrastructure/database/connection.py` |
| `redis-url` | `src/infrastructure/cache/cache_client.py` |

> **Never** store these values in `.env` files committed to version control. Use Harness Secrets or equivalent vault solutions in all non-local environments.

---

## Part 5 — Audit Log Export to Harness

The application's audit log (`src/audit/logger.py`) can be configured to forward structured audit events to Harness via its **Audit Trail API**, enabling centralized governance across all platform activities:

```
POST https://app.harness.io/audit/api/auditLogs
Content-Type: application/json
x-api-key: <HARNESS_API_KEY>

{
  "timestamp": "2026-07-07T10:00:00Z",
  "actor": "email-assistant-agent",
  "action": "EMAIL_SENT",
  "resource": "draft/abc-123",
  "outcome": "SUCCESS",
  "approvedBy": "john.doe@company.com"
}
```

---

## Part 6 — Monitoring and Alerting

Configure Harness CV (Continuous Verification) monitors on the following application metrics:

| Metric | Alert Threshold |
|---|---|
| Draft approval rejection rate | > 20% over 1 hour |
| LLM API error rate | > 5% over 5 minutes |
| Gmail send failure rate | > 2% over 5 minutes |
| Approval queue depth | > 10 pending drafts |
| Audit log write failures | Any failure |
