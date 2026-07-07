# REST API Reference

## Base URL

```
http://localhost:8000/api/v1
```

In production, replace with your deployed domain.

---

## Authentication

All endpoints (except `/health`) require a Bearer token in the `Authorization` header:

```
Authorization: Bearer <YOUR_API_TOKEN>
```

Tokens are issued by the system administrator and associated with a user role (`operator`, `reviewer`, `admin`). Token validation is handled by `src/api/middleware/auth_middleware.py`.

---

## Endpoints

---

### Health

#### `GET /health`

Returns the liveness and readiness status of the application. No authentication required.

**Response 200 OK**

```json
{
  "status": "ok",
  "version": "1.0.0",
  "environment": "production",
  "checks": {
    "database": "ok",
    "redis": "ok",
    "gmail_api": "ok",
    "llm_provider": "ok"
  }
}
```

**Response 503 Service Unavailable**

```json
{
  "status": "degraded",
  "checks": {
    "database": "ok",
    "redis": "error",
    "gmail_api": "ok",
    "llm_provider": "ok"
  }
}
```

---

### Emails

#### `POST /emails/ingest`

Manually ingest an email into the workflow. Used for testing or webhook delivery.

**Required Role:** `operator`

**Request Body**

```json
{
  "gmail_message_id": "18f2a3b4c5d6e7f8",
  "gmail_thread_id": "18f2a3b4c5d6e7f8",
  "subject": "Re: Project Proposal",
  "from": "client@example.com",
  "to": ["me@mycompany.com"],
  "body_plain": "Thanks for sending the proposal. Can you clarify the timeline?",
  "received_at": "2026-07-07T08:00:00Z"
}
```

**Response 202 Accepted**

```json
{
  "email_id": "em_01j2k3l4m5n6o7p8",
  "workflow_id": "wf_09q8r7s6t5u4v3w2",
  "status": "INGESTED",
  "message": "Email accepted. Workflow started."
}
```

---

#### `GET /emails/{email_id}`

Retrieve a stored email by its internal ID.

**Required Role:** `operator`, `reviewer`, `admin`

**Path Parameters**

| Parameter | Type | Description |
|---|---|---|
| `email_id` | string | Internal email identifier |

**Response 200 OK**

```json
{
  "email_id": "em_01j2k3l4m5n6o7p8",
  "gmail_message_id": "18f2a3b4c5d6e7f8",
  "subject": "Re: Project Proposal",
  "from": "client@example.com",
  "to": ["me@mycompany.com"],
  "body_plain": "Thanks for sending the proposal. Can you clarify the timeline?",
  "received_at": "2026-07-07T08:00:00Z",
  "workflow_status": "AWAITING_APPROVAL"
}
```

**Response 404 Not Found**

```json
{
  "error": "Email not found",
  "email_id": "em_01j2k3l4m5n6o7p8"
}
```

---

### Drafts

#### `GET /drafts`

List all drafts. Supports filtering by status.

**Required Role:** `operator`, `reviewer`, `admin`

**Query Parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `status` | string | `all` | Filter by draft status: `DRAFTED`, `AWAITING_APPROVAL`, `APPROVED`, `REJECTED`, `SENT` |
| `limit` | integer | `20` | Maximum number of results to return (max 100) |
| `offset` | integer | `0` | Pagination offset |

**Response 200 OK**

```json
{
  "total": 42,
  "limit": 20,
  "offset": 0,
  "drafts": [
    {
      "draft_id": "dr_xk2l3m4n5o6p7q8r",
      "email_id": "em_01j2k3l4m5n6o7p8",
      "subject": "Re: Project Proposal",
      "to": "client@example.com",
      "status": "AWAITING_APPROVAL",
      "created_at": "2026-07-07T08:05:00Z"
    }
  ]
}
```

---

#### `GET /drafts/{draft_id}`

Retrieve a specific draft with its full body content.

**Required Role:** `operator`, `reviewer`, `admin`

**Path Parameters**

| Parameter | Type | Description |
|---|---|---|
| `draft_id` | string | Internal draft identifier |

**Response 200 OK**

```json
{
  "draft_id": "dr_xk2l3m4n5o6p7q8r",
  "email_id": "em_01j2k3l4m5n6o7p8",
  "subject": "Re: Project Proposal",
  "to": "client@example.com",
  "body": "Dear Client,\n\nThank you for your question regarding the timeline...",
  "status": "AWAITING_APPROVAL",
  "guardrails_passed": true,
  "pii_detected": false,
  "created_at": "2026-07-07T08:05:00Z",
  "updated_at": "2026-07-07T08:05:12Z"
}
```

---

### Approvals

#### `POST /approvals/{draft_id}/decision`

Submit a human approval or rejection decision for a draft. This is the endpoint that unblocks the approval gate.

**Required Role:** `reviewer`, `admin`

**Path Parameters**

| Parameter | Type | Description |
|---|---|---|
| `draft_id` | string | Internal draft identifier |

**Request Body**

```json
{
  "decision": "APPROVED",
  "comments": "Tone and content are correct. Good to send."
}
```

| Field | Type | Required | Values |
|---|---|---|---|
| `decision` | string | Yes | `APPROVED` or `REJECTED` |
| `comments` | string | No | Free-text rationale for the decision |

**Response 200 OK (Approved)**

```json
{
  "approval_record_id": "ap_1a2b3c4d5e6f7g8h",
  "draft_id": "dr_xk2l3m4n5o6p7q8r",
  "decision": "APPROVED",
  "reviewer": "john.doe@company.com",
  "decided_at": "2026-07-07T08:15:00Z",
  "workflow_status": "SENDING",
  "message": "Draft approved. Email is being sent."
}
```

**Response 200 OK (Rejected)**

```json
{
  "approval_record_id": "ap_1a2b3c4d5e6f7g8h",
  "draft_id": "dr_xk2l3m4n5o6p7q8r",
  "decision": "REJECTED",
  "reviewer": "john.doe@company.com",
  "comments": "The timeline mentioned is incorrect.",
  "decided_at": "2026-07-07T08:15:00Z",
  "workflow_status": "TERMINATED",
  "message": "Draft rejected. Workflow terminated."
}
```

**Response 409 Conflict**

```json
{
  "error": "Draft is not in AWAITING_APPROVAL status",
  "current_status": "SENT"
}
```

---

## Error Responses

All error responses follow a consistent structure:

```json
{
  "error": "Human-readable error message",
  "code": "MACHINE_READABLE_ERROR_CODE",
  "detail": "Optional additional context"
}
```

### Common HTTP Status Codes

| Code | Meaning |
|---|---|
| `200` | Success |
| `202` | Accepted (async processing started) |
| `400` | Bad Request — invalid input |
| `401` | Unauthorized — missing or invalid token |
| `403` | Forbidden — token lacks required role |
| `404` | Not Found — resource does not exist |
| `409` | Conflict — resource is in an incompatible state |
| `429` | Too Many Requests — rate limit exceeded |
| `500` | Internal Server Error |
| `503` | Service Unavailable — dependency is down |

---

## Webhooks

### Gmail Push Notification

**`POST /webhooks/gmail`**

Receives Gmail Pub/Sub push notifications for new message events. Handled by `src/integrations/gmail/webhook_handler.py`.

**Required Header:** `X-Goog-Channel-Token: <configured-token>`

**Request Body** (sent by Google Pub/Sub)

```json
{
  "message": {
    "data": "<base64-encoded-gmail-notification>",
    "messageId": "1234567890",
    "publishTime": "2026-07-07T08:00:00Z"
  },
  "subscription": "projects/your-project/subscriptions/gmail-push-sub"
}
```

**Response 204 No Content** — Acknowledge receipt. Processing happens asynchronously.
