# Touch Base — Voice Virtual Assistant

A voice-driven project assistant built on Google ADK and Gemini Live. It connects an internal knowledge base (PDF RAG via ChromaDB) with Google Calendar (CRUD + scheduling) and a team directory.

https://github.com/user-attachments/assets/fa9c85e4-8415-4b34-940f-1c32baa7864e

---

### 📊 Project Overview
Click the preview below to view the full design deck and project goals.

[![Watch Presentation](https://github.com/user-attachments/assets/aa200f7f-2240-4d61-8164-419ae7fb7b03)](./Touch%20Base.pdf)

> 💡 **Deep Dive:** For a technical breakdown of the engine, see [APP_ARCHITECTURE.md](APP_ARCHITECTURE.md).

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
6. [RAG Pipeline](#rag-pipeline)
7. [Running the Application](#running-the-application)
8. [Project Structure](#project-structure)
9. [Troubleshooting](#troubleshooting)

---

## Prerequisites

- Python 3.11+
- A Google Cloud project with the following APIs enabled:
  - **Vertex AI API** (Gemini + embeddings)
  - **Google Calendar API**
- A service account with the `roles/aiplatform.user` role
- OAuth 2.0 Desktop credentials for Calendar access
- PDF documents to populate the knowledge base (optional but recommended)

---

## Installation

1. Clone the repository:

```bash
git clone <repo-url>
cd <repo-name>
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

The `secrets/` directory contains example template files showing the expected format for each credential. Copy them, remove the `.example` extension, and fill in your real values. The remaining configuration files must be created locally as described below.

### 1. Environment Variables (`.env`)

Create a `.env` file in the project root.

**Location:** `.env` (project root)

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
**Template:** `secrets/service_account_credentials.example.json`

**How to create:**

1. In [Google Cloud Console](https://console.cloud.google.com/), go to **IAM & Admin > Service Accounts**
2. Create a service account (e.g. `voice-assistant-sa`)
3. Grant the role: `roles/aiplatform.user`
4. Go to the **Keys** tab, click **Add Key > Create new key > JSON**
5. Download the file and save it as `secrets/service_account_credentials.json`

### 3. OAuth Client Credentials

Used for the Google Calendar OAuth 2.0 Desktop flow.

**Location:** `secrets/credentials.json`
**Template:** `secrets/credentials.example.json`

**How to create:**

1. In [Google Cloud Console](https://console.cloud.google.com/), go to **APIs & Services > Credentials**
2. Click **Create Credentials > OAuth client ID**
3. Application type: **Desktop application**
4. Download the JSON file and save it as `secrets/credentials.json`

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

After placing PDFs in `company_docs/`, run the ingestion script to build the ChromaDB vector store:

```bash
python scripts/ingest_docs.py
```

The script parses each PDF with Docling, chunks the text, generates embeddings via Vertex AI (`text-embedding-004`), and stores everything in ChromaDB. It produces:

- `chroma_db/` — the persisted ChromaDB vector store (used at runtime by the `search_project_docs` tool)
- `ingestion_cache.json` — MD5 hash cache for incremental ingestion (only new or changed files are re-processed)

Both are gitignored and generated locally. Re-run the script any time you add or update documents.

> See [RAG Pipeline](#rag-pipeline) for a detailed breakdown of the ingestion and search stack.

---

## RAG Pipeline

The document search feature (`search_project_docs` tool) is backed by a full RAG pipeline:

```
PDF files → Docling (parsing) → LangChain (chunking) → Vertex AI Embeddings → ChromaDB (vector store)
```

### Ingestion Stack

| Stage | Library | Detail |
|-------|---------|--------|
| **Parsing** | [Docling](https://github.com/DS4SD/docling) | Converts PDFs to clean Markdown, preserving structure |
| **Chunking** | LangChain `RecursiveCharacterTextSplitter` | 1 000-char chunks with 100-char overlap |
| **Embeddings** | Vertex AI `text-embedding-004` | Google's latest text embedding model via `langchain-google-vertexai` |
| **Vector Store** | [ChromaDB](https://www.trychroma.com/) | Persistent local vector database stored in `chroma_db/` |
| **Caching** | MD5 hash cache (`ingestion_cache.json`) | Only new or changed files are re-processed on subsequent runs |

### Search at Runtime

At query time, the `ChromaDocsRepository` loads the persisted ChromaDB collection and supports two retrieval strategies:

- **MMR (Maximal Marginal Relevance)** — enabled by default. Balances relevance with diversity to avoid returning near-duplicate chunks. Fetches `3 × top_k` candidates and selects the best `top_k`.
- **Similarity search** — pure cosine-similarity ranking when MMR is disabled.

An optional `score_threshold` parameter filters out low-confidence results.

### Architecture

The RAG feature follows the same clean-architecture pattern as the rest of the app:

```
DocsRepository (ABC)  →  ChromaDocsRepository (infrastructure)  →  DocsService (application)  →  search_project_docs (tool)
```

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
├── secrets/                      # Credentials directory
│   ├── credentials.example.json                  # OAuth template (committed)
│   ├── credentials.json                          # Your OAuth credentials (not committed)
│   ├── service_account_credentials.example.json  # Service account template (committed)
│   └── service_account_credentials.json          # Your service account key (not committed)
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

- Only the `.example.json` templates in `secrets/` are committed — the actual credential files are gitignored
- Never share your OAuth token (`calendar_token.json`)
- The `.env` file contains project configuration and is gitignored
