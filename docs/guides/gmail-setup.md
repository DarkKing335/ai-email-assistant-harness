# Gmail OAuth 2.0 Setup Guide

## Overview

The AI Email Assistant requires access to your Gmail account to read email threads, create drafts, and send approved replies. Access is granted via **OAuth 2.0**, which means the application never stores your Gmail password — only a short-lived access token and a refresh token that you can revoke at any time.

---

## Required Gmail API Scopes

The application requests the minimum scopes necessary for its functions:

| Scope | Purpose |
|---|---|
| `https://www.googleapis.com/auth/gmail.readonly` | Read email threads and message content |
| `https://www.googleapis.com/auth/gmail.compose` | Create and update draft replies |
| `https://www.googleapis.com/auth/gmail.send` | Send approved draft emails |
| `https://www.googleapis.com/auth/gmail.modify` | Mark messages as read after processing |

> **Note:** The `gmail.send` scope is only exercised after a human has explicitly approved a draft through the approval gate.

---

## Step 1 — Create a Google Cloud Project

1. Go to [https://console.cloud.google.com](https://console.cloud.google.com).
2. Click **Select a project** → **New Project**.
3. Enter a project name (e.g., `ai-email-assistant`) and click **Create**.
4. Select the new project from the project selector dropdown.

---

## Step 2 — Enable the Gmail API

1. In the left navigation, go to **APIs & Services** → **Library**.
2. Search for **Gmail API**.
3. Click on **Gmail API** and then click **Enable**.

---

## Step 3 — Configure the OAuth Consent Screen

1. Go to **APIs & Services** → **OAuth consent screen**.
2. Select **External** (for personal Gmail accounts) or **Internal** (for Google Workspace organizational accounts).
3. Fill in the required fields:
   - **App name:** `AI Email Assistant`
   - **User support email:** Your email address.
   - **Developer contact information:** Your email address.
4. Click **Save and Continue**.
5. On the **Scopes** page, click **Add or Remove Scopes** and add all four scopes listed above.
6. Click **Save and Continue**.
7. On the **Test users** page (External apps only), add the Gmail account the assistant will use.
8. Click **Save and Continue**, then **Back to Dashboard**.

---

## Step 4 — Create OAuth 2.0 Credentials

1. Go to **APIs & Services** → **Credentials**.
2. Click **Create Credentials** → **OAuth client ID**.
3. For **Application type**, select **Desktop app**.
4. Enter a name (e.g., `AI Email Assistant Desktop Client`).
5. Click **Create**.
6. A dialog will show your **Client ID** and **Client Secret**. Download the JSON file by clicking **Download JSON**.

---

## Step 5 — Configure the Project

Rename the downloaded credentials file and place it in the project:

```bash
mv ~/Downloads/client_secret_*.json credentials/gmail_credentials.json
```

Then add the following to your `.env` file:

```
GMAIL_CLIENT_ID=<your-client-id>
GMAIL_CLIENT_SECRET=<your-client-secret>
GMAIL_REDIRECT_URI=http://localhost:8080/oauth/callback
GMAIL_CREDENTIALS_PATH=credentials/gmail_credentials.json
GMAIL_TOKEN_PATH=credentials/gmail_token.json
```

> **Security:** Never commit `gmail_credentials.json` or `gmail_token.json` to version control. Both files are listed in `.gitignore` by default.

---

## Step 6 — Generate the Access Token

Run the token generation utility:

```bash
python tools/generate_token.py
```

1. A browser window will open and ask you to sign in to the Gmail account you want the assistant to access.
2. Review the requested permissions and click **Allow**.
3. The utility will exchange the authorization code for an access token and refresh token.
4. Both tokens are saved to `credentials/gmail_token.json`.

Expected output:

```
Opening browser for OAuth authorization...
Authorization successful.
Token saved to credentials/gmail_token.json
Gmail connection verified: reading as user@example.com
```

---

## Step 7 — Verify the Connection

After generating the token, verify that the Gmail client can connect:

```bash
python -c "from src.integrations.gmail.client import GmailClient; GmailClient().verify()"
```

Expected output:

```
Gmail API connection: OK
Authorized as: user@example.com
Unread messages: 4
```

---

## Token Refresh

The OAuth access token expires after 1 hour. The Gmail client (`src/integrations/gmail/auth.py`) automatically refreshes the access token using the stored refresh token. No manual action is required as long as the refresh token remains valid.

The refresh token becomes invalid if:
- You revoke access at [https://myaccount.google.com/permissions](https://myaccount.google.com/permissions).
- The token has not been used for 6 months.
- You change your Google account password (if 2-Step Verification is not enabled).

To re-authorize, simply re-run `python tools/generate_token.py`.

---

## Revoking Access

To revoke the assistant's access to your Gmail account at any time:

1. Go to [https://myaccount.google.com/permissions](https://myaccount.google.com/permissions).
2. Find **AI Email Assistant** and click **Remove Access**.
3. Delete `credentials/gmail_token.json` from the project to prevent stale token errors.

---

## Gmail Push Notifications (Webhook Mode)

For real-time email processing using Gmail's Pub/Sub push notifications instead of polling:

1. Create a Google Cloud Pub/Sub topic in your project.
2. Grant the Gmail service account (`gmail-api-push@system.gserviceaccount.com`) the **Pub/Sub Publisher** role on your topic.
3. Create a Pub/Sub push subscription pointing to your application's webhook endpoint (e.g., `https://your-domain.com/api/webhooks/gmail`).
4. Register the watch on the Gmail inbox by running:

```bash
python -c "from src.integrations.gmail.client import GmailClient; GmailClient().register_watch()"
```

Gmail push notifications expire every 7 days. Schedule the `register_watch()` call to run at least once every 7 days to maintain real-time delivery.
