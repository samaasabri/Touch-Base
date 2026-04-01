# Touch Base — `app/` Architecture Reference

> Use this document to answer technical questions about the codebase.

---

## Table of Contents

1. [High-Level Overview](#high-level-overview)
2. [Folder Structure](#folder-structure)
3. [Architecture Pattern — Hexagonal (Ports & Adapters)](#architecture-pattern--hexagonal-ports--adapters)
4. [Layer-by-Layer Breakdown](#layer-by-layer-breakdown)
   - [domain/](#1-domain--business-contracts)
   - [application/](#2-application--use-cases)
   - [infrastructure/](#3-infrastructure--external-adapters)
   - [touch_base/](#4-touch_base--agent--tools)
   - [api/](#5-api--websocket-transport)
   - [static/](#6-static--frontend)
   - [config.py & main.py](#7-configpy--mainpy--app-bootstrap)
5. [Request Lifecycle — End to End](#request-lifecycle--end-to-end)
6. [WebSocket Protocol](#websocket-protocol)
7. [Audio Pipeline](#audio-pipeline)
8. [Agent System & Tool Design](#agent-system--tool-design)
9. [RAG Pipeline (Knowledge Base)](#rag-pipeline-knowledge-base)
10. [Key Design Decisions & Trade-offs](#key-design-decisions--trade-offs)
11. [Tech Stack Summary](#tech-stack-summary)
12. [Common Q&A](#common-qa)

---

## High-Level Overview

**Touch Base** is a voice-driven project assistant built on [Google ADK (Agent Development Kit)](https://google.github.io/adk-docs/) and the **Gemini Live** model. It connects two pillars:

- **Internal Knowledge Base** — PDF documents ingested into a ChromaDB vector store, queried via RAG.
- **Google Calendar** — full CRUD + free/busy scheduling with automatic email invitations.

Users interact via a web UI that supports both **text chat** and **real-time voice** (bidirectional PCM audio over WebSocket).

```
┌──────────────────────────────────────────────────────┐
│                    Browser (SPA)                      │
│  index.html + app.js + AudioWorklet processors       │
└──────────────────┬──────────────────┬────────────────┘
                   │ text/plain       │ audio/pcm
                   │ (JSON)           │ (base64)
              WebSocket /ws/{session_id}?is_audio=...
                   │                  │
┌──────────────────▼──────────────────▼────────────────┐
│                  FastAPI Server                        │
│  ws_handler.py  ─►  LiveSessionService                │
│                      ├─ ADK Runner                    │
│                      └─ InMemorySessionService        │
│                              │                        │
│              ┌───────────────▼────────────────┐       │
│              │  Gemini Live 2.5 Flash Agent   │       │
│              │  (touch_base/agent.py)         │       │
│              └───┬───┬───┬───┬───┬───┬───┬───┘       │
│                  │   │   │   │   │   │   │            │
│     Tools:  list create edit del free lookup rag      │
│                  │   │   │   │   │   │   │            │
│  ┌───────────────▼───▼───▼───▼───▼───┘   │            │
│  │  CalendarService ──► GoogleCalendar   │            │
│  │  PeopleService   ──► FilePeople       │            │
│  │  DocsService     ──► ChromaDocs ◄─────┘            │
│  └───────────────────────────────────────┘            │
└──────────────────────────────────────────────────────┘
```

---

## Folder Structure

```
app/
├── __init__.py
├── main.py                          # FastAPI app factory, static files, WS endpoint
├── config.py                        # Settings dataclass loaded from .env
│
├── api/                             # Transport layer (WebSocket only)
│   └── ws_handler.py                # Bidirectional WS: text + audio, keepalive
│
├── application/                     # Use-case services (thin facades)
│   ├── calendar_service.py          # CalendarService  → CalendarRepository
│   ├── docs_service.py              # DocsService      → DocsRepository
│   ├── live_session_service.py      # ADK Runner + session + voice config
│   └── people_service.py            # PeopleService    → PeopleDirectoryRepository
│
├── domain/                          # Pure business contracts — no frameworks
│   └── ports/
│       ├── calendar_repository.py   # ABC: list / create / edit / delete / find_free_time
│       ├── docs_repository.py       # ABC: search(query, top_k, use_mmr, score_threshold)
│       └── people_directory_repository.py  # ABC: lookup_member(name)
│
├── infrastructure/                  # Concrete adapters implementing the ports
│   ├── calendar/
│   │   └── google_calendar_repository.py   # Google Calendar API v3 + OAuth2
│   ├── docs/
│   │   └── chroma_docs_repository.py       # ChromaDB + Vertex AI Embeddings
│   └── people/
│       └── file_people_directory_repository.py  # JSON file + RapidFuzz matching
│
├── touch_base/                      # Agent definition + tools
│   ├── agent.py                     # build_root_agent() — Gemini Live agent
│   ├── factories.py                 # Cached singleton factories for services
│   └── tools/
│       ├── __init__.py              # Exports all tool callables
│       ├── calendar_utils.py        # Time formatting, parsing, get_current_time
│       ├── create_event.py          # Tool → CalendarService.create_event
│       ├── delete_event.py          # Tool → CalendarService.delete_event
│       ├── edit_event.py            # Tool → CalendarService.edit_event
│       ├── find_free_time.py        # Tool → CalendarService.find_free_time
│       ├── list_events.py           # Tool → CalendarService.list_events
│       ├── lookup_team_member.py    # Tool → PeopleService.lookup_member
│       └── rag_search.py            # Tool → DocsService.search
│
└── static/                          # Frontend SPA
    ├── index.html                   # Chat UI shell + CSS (Inter font, pill composer)
    └── js/
        ├── app.js                   # WebSocket client, chat logic, audio toggle
        ├── audio-recorder.js        # Mic capture → AudioWorklet → 16-bit PCM
        ├── audio-player.js          # PCM playback → AudioWorklet @ 24 kHz
        ├── pcm-recorder-processor.js  # AudioWorkletProcessor for recording
        └── pcm-player-processor.js    # AudioWorkletProcessor ring-buffer player
```

---

## Architecture Pattern — Hexagonal (Ports & Adapters)

The project follows the **Hexagonal Architecture** (also called Ports & Adapters):

```
         ┌────────────────────────────────┐
         │          domain/ports/          │  ← Abstract contracts (ABCs)
         │  CalendarRepository (ABC)       │
         │  DocsRepository (ABC)           │
         │  PeopleDirectoryRepository(ABC) │
         └──────────┬─────────────────────┘
                    │ implements
         ┌──────────▼─────────────────────┐
         │       infrastructure/           │  ← Concrete adapters
         │  GoogleCalendarRepository       │     (Google API, ChromaDB, JSON file)
         │  ChromaDocsRepository           │
         │  FilePeopleDirectoryRepository  │
         └──────────┬─────────────────────┘
                    │ injected into
         ┌──────────▼─────────────────────┐
         │        application/             │  ← Use-case services
         │  CalendarService                │     (thin delegation layer)
         │  DocsService                    │
         │  PeopleService                  │
         └────────────────────────────────┘
```

**Why this matters:**
- **Testability** — swap any adapter with a mock/fake without touching business logic.
- **Separation of concerns** — domain layer has zero framework imports.
- **Flexibility** — switching from Google Calendar to Outlook, or from ChromaDB to Pinecone, only requires a new adapter.

---

## Layer-by-Layer Breakdown

### 1. `domain/` — Business Contracts

Contains only Python ABCs (Abstract Base Classes). No framework dependencies.

| Port | Methods | Purpose |
|------|---------|---------|
| `CalendarRepository` | `list_events`, `create_event`, `edit_event`, `delete_event`, `find_free_time` | Calendar CRUD + availability |
| `DocsRepository` | `search(query, top_k, use_mmr, score_threshold)` | Vector search over documents |
| `PeopleDirectoryRepository` | `lookup_member(name)` | Fuzzy name → email lookup |

### 2. `application/` — Use Cases

Thin service classes that accept a port interface via constructor injection and delegate calls. This layer exists to:
- Provide a single entry point for each business capability.
- Allow adding cross-cutting concerns (logging, validation, caching) without touching infrastructure.

**`LiveSessionService`** is special — it wires the ADK `Runner` with `InMemorySessionService` and configures the voice:

```python
run_config = RunConfig(
    response_modalities=["AUDIO"],
    speech_config=SpeechConfig(
        voice_config=VoiceConfig(
            prebuilt_voice_config=PrebuiltVoiceConfig(voice_name="Puck")
        )
    ),
    output_audio_transcription={},
)
```

Key detail: `output_audio_transcription={}` enables the model to send **text transcriptions alongside audio**, which is how the chat shows written text even in voice mode.

### 3. `infrastructure/` — External Adapters

| Adapter | Implements | External Dependency | Notes |
|---------|-----------|-------------------|-------|
| `GoogleCalendarRepository` | `CalendarRepository` | Google Calendar API v3 | OAuth2 Desktop flow; token at `~/.credentials/calendar_token.json`; auto-refresh. Free/busy checks 9 AM–5 PM with merged interval algorithm. |
| `ChromaDocsRepository` | `DocsRepository` | ChromaDB + `VertexAIEmbeddings` (`text-embedding-004`) | Lazy-loaded vectorstore singleton. Supports both **MMR** (Maximal Marginal Relevance) and plain similarity search. |
| `FilePeopleDirectoryRepository` | `PeopleDirectoryRepository` | `team_directory.json` + RapidFuzz | Fuzzy matching with `WRatio` scorer; threshold = 60; returns top 3 matches. |

#### Google Calendar — OAuth Flow

```
credentials.json (OAuth client secret)
        │
        ▼
InstalledAppFlow.run_local_server()
        │
        ▼
calendar_token.json (refresh + access tokens)
        │
        ▼
Credentials.refresh(Request())  ← auto-refresh on expiry
```

#### Free/Busy Algorithm (`find_free_time`)

1. Query Google Freebusy API for the owner's primary calendar + all attendee emails.
2. Collect all busy intervals, merge overlapping ones.
3. Walk 9:00–17:00 window, emit gaps that fit the requested `duration_minutes`.

### 4. `touch_base/` — Agent & Tools

#### `agent.py` — `build_root_agent()`

Creates a Google ADK `Agent` with:
- **Model:** `gemini-live-2.5-flash-native-audio`
- **7 tools** bound as plain Python functions (ADK auto-converts them to function declarations for the model).
- **System instruction** covering: language/dialect mirroring, mandatory "hold line" before tool calls, Arabic name transliteration, calendar conventions, and RAG usage rules.

#### `factories.py` — Singleton Wiring

Uses `@lru_cache(maxsize=1)` to create one instance of each service for the process lifetime:

```python
@lru_cache(maxsize=1)
def get_calendar_service() -> CalendarService:
    return CalendarService(GoogleCalendarRepository(get_settings()))
```

This means all tools share the same service instances — no redundant OAuth handshakes or ChromaDB connections.

#### `tools/` — Agent-Callable Functions

Each tool module is a thin wrapper that calls the corresponding application service via `factories.py`:

```
Tool function  ──►  factories.get_*_service()  ──►  ApplicationService  ──►  Port  ──►  Adapter
```

| Tool | Parameters | Returns | What It Does |
|------|-----------|---------|--------------|
| `list_events` | `start_date: str`, `days: int` | `dict` with events array | List calendar events for a date range |
| `create_event` | `summary`, `start_time`, `end_time`, `attendees?` | `dict` with event_id | Create event + send email invitations |
| `edit_event` | `event_id`, `summary`, `start_time`, `end_time` | `dict` | Modify an existing event |
| `delete_event` | `event_id`, `confirm: bool` | `dict` | Delete with explicit confirmation |
| `find_free_time` | `date`, `duration_minutes?=15`, `emails?` | `list` of free slots | Multi-person availability via Freebusy API |
| `lookup_team_member` | `name: str` | `dict` with matches | Fuzzy name search in team directory |
| `search_project_docs` | `query`, `top_k?=5`, `use_mmr?=True`, `score_threshold?` | `str` formatted results | RAG search over ingested PDFs |

`calendar_utils.py` also provides `get_current_time()` which is injected into the system prompt as an f-string so the agent always knows the current date/time.

### 5. `api/` — WebSocket Transport

`ws_handler.py` manages the bidirectional WebSocket between browser and ADK agent using three concurrent `asyncio` tasks:

| Task | Direction | What It Does |
|------|-----------|--------------|
| `agent_to_client_messaging` | Agent → Browser | Streams `text/plain` (partial text) and `audio/pcm` (base64-encoded) events |
| `client_to_agent_messaging` | Browser → Agent | Receives JSON messages, dispatches to `LiveRequestQueue` as `Content` (text) or `Blob` (audio) |
| `keepalive_ping` | Server → Browser | Sends `{"type":"ping"}` every 20 seconds to prevent idle disconnections |

These three tasks run via `asyncio.wait(FIRST_COMPLETED)` — when any task finishes (e.g., client disconnects), the others are cancelled and the request queue is closed.

**Turn signaling:** When the agent finishes a response turn, it sends `{"turn_complete": true}`. The frontend uses this to stop the typing indicator and prepare for the next user input.

### 6. `static/` — Frontend

A single-page app with no build step.

#### `index.html`
- Clean, minimal chat UI with Inter font.
- `__PUBLIC_APP_URL__` placeholder replaced server-side for demo-friendly branding.
- Typing indicator with bouncing dots animation.
- Responsive layout (mobile breakpoint at 600px).

#### `app.js` — Client Logic
- **Session ID:** Random string generated on page load — unique per tab.
- **WebSocket:** Auto-reconnects on close (5-second delay).
- **Message streaming:** Agent text arrives in partial chunks per turn; the JS appends to the same `<p>` element until `turn_complete`.
- **Audio toggle:** Clicking the mic button starts audio worklets and reconnects the WS with `is_audio=true`.

#### Audio Worklet Architecture

```
Microphone (16 kHz mono)
    │
    ▼
pcm-recorder-processor.js     ← AudioWorkletProcessor: captures Float32 frames
    │
    ▼
audio-recorder.js              ← Converts Float32 → Int16 PCM
    │
    ▼
app.js → WebSocket             ← Base64-encodes and sends as {"mime_type":"audio/pcm"}
    │
    ▼
Server (ADK LiveRequestQueue)
    │ (Agent generates audio response)
    ▼
WebSocket → app.js             ← Receives base64 audio/pcm
    │
    ▼
pcm-player-processor.js        ← AudioWorkletProcessor: ring buffer (24 kHz, 180s capacity)
    │
    ▼
Speaker output (24 kHz)
```

**Sample rates:** Input is 16 kHz (optimal for speech recognition), output is 24 kHz (Gemini's native audio output rate).

**Ring buffer:** The player uses a circular buffer of `24000 × 180 = 4,320,000` Float32 samples (180 seconds). On overflow, oldest samples are overwritten.

### 7. `config.py` & `main.py` — App Bootstrap

#### `config.py`

Frozen `Settings` dataclass populated from `.env` via `python-dotenv`. Key settings:

| Setting | Default | Source |
|---------|---------|--------|
| `app_name` | `"ADK Streaming example"` | `APP_NAME` env var |
| `voice_name` | `"Puck"` | `VOICE_NAME` env var |
| `timezone_fallback` | `"Africa/Cairo"` | `TIMEZONE_FALLBACK` env var |
| `public_app_url` | `"local"` | `PUBLIC_APP_URL` env var |
| `calendar_token_path` | `~/.credentials/calendar_token.json` | `CALENDAR_TOKEN_PATH` env var |
| `credentials_path` | `secrets/credentials.json` | `GOOGLE_OAUTH_CREDENTIALS_PATH` env var |

#### `main.py` — `create_app()`

1. Loads `Settings`.
2. Mounts `app/static` for static file serving.
3. Reads `index.html` as a template, replaces `__PUBLIC_APP_URL__` with the configured value.
4. Creates a single `LiveSessionService` instance with the root agent.
5. Registers the WebSocket endpoint at `/ws/{session_id}`.

Run with:
```bash
uvicorn app.main:app --reload
```

---

## Request Lifecycle — End to End

### Text Message Flow

```
1. User types "What meetings do I have today?" and hits Send
2. app.js sends via WS: {"mime_type":"text/plain","data":"What meetings...","role":"user"}
3. ws_handler.py → client_to_agent_messaging() → LiveRequestQueue.send_content()
4. ADK Runner delivers message to Gemini Live agent
5. Agent decides to call list_events tool (today's date, days=1)
6. list_events → factories.get_calendar_service() → GoogleCalendarRepository.list_events()
7. Google Calendar API returns events
8. Agent formulates natural language response
9. ADK emits Event objects (partial=True for streaming text)
10. ws_handler.py → agent_to_client_messaging() → sends JSON chunks to browser
11. app.js appends text to the agent bubble in real-time
12. ADK emits turn_complete=True → typing indicator hides
```

### Voice Message Flow

Same as above, but:
- Step 2 sends `audio/pcm` (base64) instead of `text/plain`.
- Step 3 uses `LiveRequestQueue.send_realtime()` with a `Blob`.
- Steps 9–10 also include `audio/pcm` inline data alongside text transcriptions.
- The browser plays audio through the PCM player worklet.

---

## WebSocket Protocol

All messages are JSON strings over a single WebSocket connection at `/ws/{session_id}?is_audio=true|false`.

### Client → Server

| Field | Type | Description |
|-------|------|-------------|
| `mime_type` | `"text/plain"` or `"audio/pcm"` | Message format |
| `data` | `string` | Text content or base64-encoded PCM bytes |
| `role` | `"user"` (default) | Sender role |

### Server → Client

| Message Type | Fields | When |
|-------------|--------|------|
| Text chunk | `{"mime_type":"text/plain","data":"...","role":"model"}` | Partial agent text |
| Audio chunk | `{"mime_type":"audio/pcm","data":"<base64>","role":"model"}` | Agent audio output |
| Turn complete | `{"turn_complete":true,"interrupted":false}` | Agent finished responding |
| Interrupted | `{"turn_complete":false,"interrupted":true}` | User interrupted agent |
| Keepalive | `{"type":"ping"}` | Every 20 seconds |

---

## Audio Pipeline

| Stage | Sample Rate | Format | Location |
|-------|-------------|--------|----------|
| Mic capture | 16 kHz | Float32 | `pcm-recorder-processor.js` |
| Pre-send conversion | 16 kHz | Int16 PCM | `audio-recorder.js` |
| WebSocket transport | — | Base64 string | `app.js` ↔ `ws_handler.py` |
| Agent processing | — | Raw bytes | ADK `LiveRequestQueue.send_realtime()` |
| Agent output | 24 kHz | Int16 PCM (base64) | `ws_handler.py` → browser |
| Playback | 24 kHz | Float32 (ring buffer) | `pcm-player-processor.js` |

The asymmetric sample rates (16 kHz in, 24 kHz out) reflect optimal rates for speech recognition input vs. the Gemini model's native audio generation output.

---

## Agent System & Tool Design

### How ADK Function Tools Work

Google ADK auto-introspects Python function signatures and docstrings to generate JSON Schema tool declarations for the Gemini model. Each tool in `touch_base/tools/` is a plain function:

```python
def create_event(summary: str, start_time: str, end_time: str,
                 attendees: Optional[list[str]] = None) -> dict:
    return get_calendar_service().create_event(summary, start_time, end_time, attendees)
```

The model sees this as a callable tool and autonomously decides when to invoke it based on the system instruction and user intent.

### System Instruction Highlights

The agent's prompt in `agent.py` encodes several behavioral rules:

- **Language mirroring** — detects the user's language, dialect, and code-mixing patterns and replies in kind (e.g., Egyptian Arabic, British English).
- **Mandatory hold line** — before every tool call, the agent first sends a short wait phrase ("One sec," / "ثانية معايا"), then calls the tool, then responds with results in a separate turn. This avoids a silent gap while tools execute.
- **Arabic name transliteration** — Arabic script names are translated to English before calling `lookup_team_member` (the fuzzy matcher works on Latin script).
- **Scheduling flow** — multi-step: lookup → confirm → find_free_time → create_event with attendee invitations.

---

## RAG Pipeline (Knowledge Base)

### Ingestion (offline, via `scripts/ingest_docs.py`)

```
company_docs/*.pdf  →  text extraction  →  chunking  →  VertexAI Embeddings  →  ChromaDB
                                                          (text-embedding-004)      (chroma_db/)
```

### Query (runtime, via `search_project_docs` tool)

```
User question → Agent calls search_project_docs(query)
                        │
                        ▼
              ChromaDocsRepository.search()
                        │
         ┌──────────────┴──────────────┐
         │ use_mmr=True (default)      │ use_mmr=False
         ▼                             ▼
  max_marginal_relevance_search   similarity_search
  (diverse results, fetch_k=15)   (pure cosine sim)
         │                             │
         └──────────────┬──────────────┘
                        ▼
              Format as "[Source N: filename]\n content"
                        │
                        ▼
              Agent synthesizes natural answer
```

**MMR** is used by default to balance relevance and diversity — avoids returning 5 nearly-identical chunks from the same page.

---

## Key Design Decisions & Trade-offs

| Decision | Rationale |
|----------|-----------|
| **Hexagonal Architecture** | Clean separation for a demo/MVP that may swap integrations (e.g., Outlook instead of Google Calendar). |
| **`@lru_cache` singletons** | Avoids repeated OAuth handshakes and ChromaDB connections. Trade-off: no hot-reload of config without restart. |
| **`InMemorySessionService`** | Good enough for single-instance demos. No persistence across server restarts — sessions are ephemeral. |
| **AudioWorklet (not ScriptProcessorNode)** | Runs on a dedicated audio thread — avoids glitches from main-thread blocking. Requires HTTPS or localhost. |
| **Ring buffer for playback** | Simple, lock-free, bounded memory. 180 seconds is generous for voice responses. |
| **Single WebSocket per session** | Both text and audio share one connection. Simplifies reconnect logic and avoids ordering issues. |
| **Base64 for audio transport** | WebSocket text frames are used (not binary) to keep the JSON protocol uniform. ~33% overhead is acceptable for voice. |
| **`frozen=True` on Settings** | Prevents accidental mutation; makes the configuration immutable after creation. |
| **Tools as plain functions** | ADK auto-generates the tool schema from type hints. No boilerplate — just write a function with a typed signature. |
| **`PUBLIC_APP_URL` injection** | For demos: the browser bar can show `https://touch-base.internal` instead of `localhost:8000` via hosts file mapping. |

---

## Tech Stack Summary

| Layer | Technology |
|-------|-----------|
| **LLM** | Gemini Live 2.5 Flash (native audio) via Vertex AI |
| **Agent Framework** | Google ADK (`google-adk`) |
| **Embeddings** | Vertex AI `text-embedding-004` |
| **Vector Store** | ChromaDB (local, persistent) |
| **Backend** | FastAPI + Uvicorn |
| **Calendar** | Google Calendar API v3 (OAuth2 Desktop) |
| **Fuzzy Matching** | RapidFuzz (`WRatio` scorer) |
| **Frontend** | Vanilla HTML/CSS/JS (no framework, no build step) |
| **Audio** | Web Audio API + AudioWorklet |
| **Config** | python-dotenv + `@dataclass(frozen=True)` |
| **Auth** | Google OAuth2 (calendar), Service Account (Vertex AI) |

---

## Common Q&A

### "Why not use REST endpoints instead of WebSocket?"

The Gemini Live model streams audio and text in real-time. WebSocket gives us a persistent bidirectional channel — essential for continuous audio streaming (mic → server → speaker) without the overhead of repeated HTTP connections.

### "How do you handle concurrent users?"

Each WebSocket connection gets its own `session_id`, `LiveRequestQueue`, and `Runner.run_live()` coroutine. ADK's `InMemorySessionService` manages sessions in a dict keyed by ID. The async architecture (FastAPI + asyncio) handles concurrency without threads.

### "What happens if the Google Calendar token expires?"

`GoogleCalendarRepository._get_calendar_service()` checks `creds.valid` on every call. If expired but a refresh token exists, it silently refreshes. If refresh fails, the user must re-run `scripts/setup_calendar_auth.py`.

### "Why RapidFuzz for name lookup instead of exact match?"

Voice input produces varied spellings ("Sara" vs "Sarah" vs "Sahar"). `WRatio` handles partial matches, abbreviations, and transliteration errors. The threshold of 60 is permissive enough for voice-to-text artifacts.

### "Why is the recording at 16 kHz but playback at 24 kHz?"

16 kHz is the standard for speech recognition (captures the full speech frequency range while minimizing data). 24 kHz is the Gemini model's native audio output rate — higher fidelity for the synthesized voice response.

### "How does the typing indicator work?"

1. When the browser sends a text message, JS immediately shows the typing indicator.
2. When the first text/audio chunk arrives from the server, the indicator stays visible (agent is still generating).
3. When the server sends `turn_complete: true`, JS hides the indicator.

### "Can you swap ChromaDB for another vector store?"

Yes. Implement a new class that extends `DocsRepository` (the port), wire it in `factories.py`, and nothing else changes. This is the core benefit of the hexagonal architecture.

### "Why is there no database?"

This is a demo/MVP. Sessions live in memory (`InMemorySessionService`). The team directory is a JSON file. The vector store (ChromaDB) is file-based. For production, you'd swap these for persistent stores.

### "How does the agent decide which tool to call?"

The Gemini model receives the system instruction (with all behavioral rules) plus the tool declarations (auto-generated from Python function signatures and type hints). It uses function-calling to decide — the model outputs a structured tool call, ADK executes it, and feeds the result back to the model for the final response.

### "What is the `__PUBLIC_APP_URL__` mechanism?"

For demos, you don't want the audience to see `http://127.0.0.1:8000` in the browser. The `index.html` has a placeholder `__PUBLIC_APP_URL__` in a `data-` attribute. At server startup, `main.py` reads the HTML file and replaces it with the configured URL (or `"local"` to show the real origin). Combined with a hosts file entry, the app appears to run on a branded domain.
