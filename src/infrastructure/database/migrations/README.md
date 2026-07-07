# Database Migrations

This directory contains all database schema migrations managed by **Alembic**.

## Running Migrations

Apply all pending migrations to bring the database to the latest schema:

```bash
alembic upgrade head
```

Roll back the most recent migration:

```bash
alembic downgrade -1
```

Roll back to a specific revision:

```bash
alembic downgrade <revision_id>
```

## Creating a New Migration

After modifying a domain model in `src/models/`, generate a new migration automatically:

```bash
alembic revision --autogenerate -m "describe_your_change"
```

Always review the generated migration file before applying it. Auto-generated migrations may not capture all changes (e.g., custom index names, partial indexes, or enum type changes).

## Migration File Naming Convention

```
<timestamp>_<short_description>.py
```

Example: `20260707_001_create_emails_table.py`

## Current Schema Tables

| Table | Domain Model | Description |
|---|---|---|
| `emails` | `Email` | Stores all ingested email messages |
| `drafts` | `Draft` | Stores all agent-generated draft replies |
| `approval_records` | `ApprovalRecord` | Stores all human approval decisions |
| `audit_events` | `AuditEvent` | Append-only audit log table |
| `users` | `User` | Stores system user accounts and roles |
| `memories` | — | Long-term memory store for the agent |
