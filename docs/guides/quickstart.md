# Quickstart Guide

## Prerequisites

Before you begin, ensure the following are installed and available on your system:

| Requirement | Minimum Version | Check Command |
|---|---|---|
| Python | 3.11+ | `python --version` |
| pip | 23+ | `pip --version` |
| Git | 2.40+ | `git --version` |
| Redis | 7+ | `redis-server --version` |
| PostgreSQL | 15+ (or SQLite for local dev) | `psql --version` |

You will also need:
- A Google Cloud project with the Gmail API enabled.
- A Gmail OAuth 2.0 Client ID and Client Secret (see [`gmail-setup.md`](./gmail-setup.md)).
- An OpenAI API key **or** a Google Gemini API key for the LLM backend.

---

## Step 1 — Clone the Repository

```bash
git clone https://github.com/your-org/ai-email-assistant-harness.git
cd ai-email-assistant-harness
```

---

## Step 2 — Create and Activate a Virtual Environment

```bash
python -m venv .venv

# macOS / Linux
source .venv/bin/activate

# Windows (PowerShell)
.venv\Scripts\Activate.ps1
```

---

## Step 3 — Install Dependencies

```bash
pip install -r requirements.txt
```

For development (includes testing and linting tools):

```bash
pip install -r requirements-dev.txt
```

---

## Step 4 — Configure Environment Variables

Copy the example environment file and fill in your values:

```bash
cp .env.example .env
```

Open `.env` and set the following required variables:

```
# LLM Provider (choose one)
OPENAI_API_KEY=sk-...
# or
GEMINI_API_KEY=AI...

# Gmail OAuth (see gmail-setup.md)
GMAIL_CLIENT_ID=...
GMAIL_CLIENT_SECRET=...
GMAIL_REDIRECT_URI=http://localhost:8080/oauth/callback

# Database
DATABASE_URL=sqlite:///./dev.db    # SQLite for local dev
# DATABASE_URL=postgresql://user:password@localhost:5432/email_assistant

# Redis (for cache and task queue)
REDIS_URL=redis://localhost:6379/0

# Application
APP_ENV=development
LOG_LEVEL=INFO
```

---

## Step 5 — Validate Configuration

Use the developer utility to catch configuration errors before starting:

```bash
python tools/validate_config.py
```

Expected output:
```
✓ LLM provider credentials found
✓ Gmail credentials found
✓ Database URL configured
✓ Redis URL configured
All configuration checks passed.
```

---

## Step 6 — Run Database Migrations

```bash
alembic upgrade head
```

---

## Step 7 — Generate a Gmail OAuth Token

Follow the interactive token generation flow:

```bash
python tools/generate_token.py
```

This will open a browser window asking you to authorize the application. After authorization, the token will be stored securely at the path configured in your `.env` file.

---

## Step 8 — (Optional) Seed the Test Inbox

To test the full workflow without a real incoming email, seed your Gmail sandbox inbox with sample messages:

```bash
python tools/seed_inbox.py
```

---

## Step 9 — Start the Assistant

### Using the CLI (recommended for first run)

Run the assistant in polling mode — it will check for new emails every 60 seconds:

```bash
python -m src.cli.main run --mode polling
```

### Using the REST API

Start the FastAPI server:

```bash
uvicorn src.api.main:app --reload --port 8000
```

API documentation will be available at: `http://localhost:8000/docs`

---

## Step 10 — Review and Approve a Draft

When the assistant processes an email and generates a draft, it will appear in the approval queue. Use the CLI to review and approve it:

```bash
# List all pending drafts
python -m src.cli.main review

# Approve a specific draft by ID
python -m src.cli.main approve --draft-id <DRAFT_ID>

# Reject a draft with a reason
python -m src.cli.main approve --draft-id <DRAFT_ID> --reject --reason "Tone is too formal"
```

---

## Step 11 — View the Audit Log

```bash
python -m src.cli.main audit --last 10
```

---

## Common Issues

| Issue | Solution |
|---|---|
| `Gmail API not enabled` | Enable the Gmail API in your Google Cloud Console |
| `Token expired` | Re-run `python tools/generate_token.py` |
| `Redis connection refused` | Ensure Redis is running: `redis-server` |
| `Database not found` | Run `alembic upgrade head` |
| `LLM API rate limit` | Add `OPENAI_REQUEST_DELAY_MS=500` to your `.env` |
