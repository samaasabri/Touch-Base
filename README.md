# Touch Base — Voice Virtual Assistant

A voice-driven project assistant built on Google ADK and Gemini Live. It connects an internal knowledge base (PDF RAG via ChromaDB) with Google Calendar (CRUD + scheduling) and a team directory (fuzzy name-to-email lookup). Users interact through a web UI supporting both text chat and real-time bidirectional voice.

> For a deep dive into the architecture, see [APP_ARCHITECTURE.md](APP_ARCHITECTURE.md).

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Configuration](#configuration)
   - [Environment Variables (.env)](#1-environment-variables-env)
   - [Service Account Credentials](#2-service-account-credentials)
   - [OAuth Client Credentials](#3-oauth-client-credentials)
   - [Team Directory](#4-team-directory)
   - [Company Documents (RAG)](#5-company-documents-rag)
4. [Calendar OAuth Setup](#calendar-oauth-setup)
5. [Ingest Documents](#ingest-documents)
6. [Running the Application](#running-the-application)
7. [Project Structure](#project-structure)
8. [Troubleshooting](#troubleshooting)

---

## Prerequisites

- Python 3.11+
- A Google Cloud project with the following APIs enabled:
  - **Vertex AI API**
  - **Google Calendar API**
- A service account with the `roles/aiplatform.user` role
- OAuth 2.0 Desktop credentials for Calendar access

---

## Installation

1. Clone the repository:

```bash
git clone https://github.com/samaasabri/Touch-Base.git
```

2. Create and activate a virtual environment:

```bash
python -m venv .venv
```

On Windows (cmd):
```bash
.venv\Scripts\activate
```

On Windows (PowerShell):
```bash
.venv\Scripts\Activate.ps1
```

On macOS/Linux:
```bash
source .venv/bin/activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

---

## Configuration

The following files are **not committed** to the repository and must be created locally. Each section below shows the expected location, format, and an example.

### 1. Environment Variables (`.env`)

Create a `.env` file in the project root.

**Location:** `.env`

**Example:**

```env
GOOGLE_GENAI_USE_VERTEXAI=TRUE
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=secrets/service_account_credentials.json
```

**Optional variables** (with their defaults):

| Variable | Default | Description |
|----------|---------|-------------|
| `GOOGLE_GENAI_USE_VERTEXAI` | `TRUE` | Enable Vertex AI backend |
| `GOOGLE_CLOUD_PROJECT` | *(required)* | Your Google Cloud project ID |
| `GOOGLE_CLOUD_LOCATION` | `us-central1` | GCP region for Vertex AI |
| `GOOGLE_APPLICATION_CREDENTIALS` | `secrets/service_account_credentials.json` | Path to service account key |
| `CALENDAR_TOKEN_PATH` | `~/.credentials/calendar_token.json` | Where the Calendar OAuth token is stored |
| `GOOGLE_OAUTH_CREDENTIALS_PATH` | `secrets/credentials.json` | Path to OAuth client credentials |
| `APP_NAME` | `ADK Streaming example` | Application display name |
| `VOICE_NAME` | `Puck` | Gemini voice name |
| `TIMEZONE_FALLBACK` | `Africa/Cairo` | Fallback timezone |
| `PUBLIC_APP_URL` | `https://touch-base.internal` | URL shown in the UI (use `local` to show real origin) |

### 2. Service Account Credentials

Used for Vertex AI authentication (embeddings + Gemini).

**Location:** `secrets/service_account_credentials.json`

**How to create:**

1. In [Google Cloud Console](https://console.cloud.google.com/), go to **IAM & Admin > Service Accounts**
2. Create a service account (e.g. `voice-assistant-sa`)
3. Grant the role: `roles/aiplatform.user`
4. Go to the **Keys** tab, click **Add Key > Create new key > JSON**
5. Download the file and place it at `secrets/service_account_credentials.json`

**Example structure:**

```json
{
  "type": "service_account",
  "project_id": "your-gcp-project-id",
  "private_key_id": "key-id-here",
  "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
  "client_email": "voice-assistant-sa@your-gcp-project-id.iam.gserviceaccount.com",
  "client_id": "123456789",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/..."
}
```

### 3. OAuth Client Credentials

Used for the Google Calendar OAuth 2.0 Desktop flow.

**Location:** `secrets/credentials.json`

**How to create:**

1. In [Google Cloud Console](https://console.cloud.google.com/), go to **APIs & Services > Credentials**
2. Click **Create Credentials > OAuth client ID**
3. Application type: **Desktop application**
4. Download the JSON file and place it at `secrets/credentials.json`

**Example structure:**

```json
{
  "installed": {
    "client_id": "123456789-abcdef.apps.googleusercontent.com",
    "project_id": "your-gcp-project-id",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_secret": "GOCSPX-your-client-secret",
    "redirect_uris": ["http://localhost"]
  }
}
```

### 4. Team Directory

Used by the `lookup_team_member` tool for fuzzy name-to-email matching (powered by RapidFuzz).

**Location:** `team_directory.json` (project root, **tracked in git**)

**Format:**

```json
{
  "team": [
    { "name": "Full Name", "email": "name@company.com" },
    { "name": "Another Person", "email": "another@company.com" }
  ]
}
```

Edit `team_directory.json` to add your actual team members. The fuzzy matcher uses RapidFuzz's `WRatio` scorer with a threshold of 60, so slight spelling differences (e.g. "Sara" vs "Sarah") are handled automatically.

### 5. Company Documents (RAG)

Place PDF files in the `company_docs/` directory for ingestion into the ChromaDB vector store. Only **PDF files** are supported.

**Location:** `company_docs/` (project root, not tracked in git)

```bash
mkdir company_docs
# Copy your PDF files into company_docs/
```

---

## Calendar OAuth Setup

After placing `secrets/credentials.json`, run the setup script to complete the OAuth flow:

```bash
python scripts/setup_calendar_auth.py
```

This will:
1. Open your browser for Google account authorization
2. Save the OAuth token to `~/.credentials/calendar_token.json` (or the path set in `CALENDAR_TOKEN_PATH`)
3. Test the connection to your Google Calendar

---

## Ingest Documents

After placing PDFs in `company_docs/`, run the ingestion script:

```bash
python scripts/ingest_docs.py
```

This generates:
- `chroma_db/` — the ChromaDB vector store (used at runtime by the `search_project_docs` tool)
- `ingestion_cache.json` — hash cache for incremental ingestion (only new/changed files are re-processed)

Both are gitignored and generated locally.

---

## Running the Application

From the project root:

```bash
uvicorn app.main:app --reload
```

Then open your browser to `http://localhost:8000`. The web UI supports both text chat and voice (click the mic button to toggle voice mode).

---

## Project Structure

```
├── .env                          # Environment variables (not committed)
├── team_directory.json           # Team name/email directory (committed)
├── requirements.txt              # Python dependencies
├── APP_ARCHITECTURE.md           # Detailed architecture reference
├── README.md                     # This file
│
├── secrets/                      # Credentials (not committed)
│   ├── credentials.json          # Google OAuth client credentials
│   └── service_account_credentials.json  # Vertex AI service account key
│
├── company_docs/                 # PDF corpus for RAG (not committed)
│   └── *.pdf
│
├── chroma_db/                    # Generated vector store (not committed)
├── ingestion_cache.json          # Generated ingestion cache (not committed)
│
├── scripts/
│   ├── setup_calendar_auth.py    # OAuth setup for Google Calendar
│   └── ingest_docs.py            # PDF ingestion into ChromaDB
│
└── app/
    ├── main.py                   # FastAPI app factory + WebSocket endpoint
    ├── config.py                 # Settings dataclass from .env
    ├── api/
    │   └── ws_handler.py         # Bidirectional WebSocket handler
    ├── application/              # Use-case services
    ├── domain/ports/             # Abstract contracts (ABCs)
    ├── infrastructure/           # Concrete adapters (Google Calendar, ChromaDB, RapidFuzz)
    ├── touch_base/               # Agent definition + tools
    │   ├── agent.py              # Gemini Live agent with system instructions
    │   ├── factories.py          # Singleton service wiring
    │   └── tools/                # 7 agent-callable tool functions
    └── static/                   # Frontend SPA (HTML + vanilla JS)
```

---

## Troubleshooting

### Calendar token errors

If you get authentication errors when using calendar features:

1. Delete the existing token:
   - Default location: `~/.credentials/calendar_token.json`
   - Or the path set in `CALENDAR_TOKEN_PATH`
2. Re-run the OAuth flow:

```bash
python scripts/setup_calendar_auth.py
```

### RAG search returns no results

Make sure you have:
1. Placed PDF files in `company_docs/`
2. Run `python scripts/ingest_docs.py` to generate the vector store
3. The `chroma_db/` directory exists and contains data

### Team member lookup fails

Verify that `team_directory.json` exists at the project root and contains a valid `"team"` array with `"name"` and `"email"` fields.

### Vertex AI authentication errors

Check that:
1. `secrets/service_account_credentials.json` exists and is valid
2. `GOOGLE_APPLICATION_CREDENTIALS` in `.env` points to the correct path
3. The service account has the `roles/aiplatform.user` role
4. The Vertex AI API is enabled in your Google Cloud project

### Security reminders

- Never commit files in `secrets/` — they are gitignored
- Never share your OAuth token (`calendar_token.json`)
- The `.env` file contains project configuration and is gitignored
