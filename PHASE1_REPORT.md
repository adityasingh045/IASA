# IASA Phase 1 — Implementation Report
**Date:** 6 November 2026  
**Phase:** 1 — IASA Foundation + Campus Guardian + F.R.I.D.A.Y Connectors  
**Status:** ✅ Complete — all tests passing  

---

## Phase 1 scope (from Phase 0 implementation plan)

- [x] IASA project scaffold created
- [x] `.env.example` written with all required vars (no real secrets)
- [x] FastAPI backend with modular structure
- [x] Database models (SQLAlchemy async, PostgreSQL-ready, SQLite for dev)
- [x] Auth skeleton: permission classes (READ/CONTROLLED/RESTRICTED), role map
- [x] Connector registry + connector base class
- [x] LLM provider adapter interface (abstract, swappable)
- [x] Campus Guardian connector — 10 tools, all verified against source code
- [x] F.R.I.D.A.Y hub connector — 4 tools, WebSocket client with AUTH flow
- [x] API layer: health, tool discovery, chat/orchestration, tool execution
- [x] Intent matching (keyword-based; LLM routing in Phase 5)
- [x] Approval flow for CONTROLLED and RESTRICTED actions
- [x] Backend running on port 8000, all endpoints verified

---

## Files created or changed

### New files (Phase 1)

```
backend/
├── requirements.txt                 # Python dependencies
├── app/
│   ├── main.py                      # FastAPI app entry point; lifespan; connector registration
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py                # ISA settings (.all from env; no hardcoding)
│   │   ├── llm_adapter.py           # Abstract LLM adapter + provider registry
│   │   ├── connector_base.py        # BaseConnector, ToolDefinition, ConnectorResult, BaseHTTPConnector
│   │   └── errors.py                # ISAError, LLMError, ConnectorError, PermissionDeniedError, etc.
│   ├── database/
│   │   ├── __init__.py
│   │   ├── session.py               # async SQLAlchemy engine (PostgreSQL; SQLite for dev)
│   │   └── models.py                # User, Workspace, Conversation, Message, ToolRegistration,
│   │                                #   ToolExecution, Approval, Memory, Event
│   ├── registry/
│   │   ├── __init__.py
│   │   └── connector_registry.py    # ConnectorRegistry singleton; health_all(), find_tool()
│   ├── auth/
│   │   ├── __init__.py
│   │   └── permissions.py           # PermissionClass, can_perform(), require_permission(),
│   │                                  classify_action()
│   ├── integrations/
│   │   ├── __init__.py
│   │   ├── connector_campus_guardian.py   # Campus Guardian connector — 10 tools
│   │   └── connector_friday.py            # F.R.I.D.A.Y hub connector — 4 tools
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes_health.py         # GET /api/health — ISA + per-project status
│   │   ├── routes_tools.py          # GET /api/tools — tool discovery
│   │   └── routes_chat.py           # POST /api/chat + POST /api/tools/execute
│   ├── memory/
│   │   └── __init__.py
│   ├── workers/
│   │   └── __init__.py
│   └── monitoring/
│   │   └── __init__.py
└── .env.example                      # Full env template with descriptions
```

### Updated files (Phase 0 audit)

```
audit/
└── PHASE0_AUDIT.md                 # Updated: F.R.I.D.A.Y confirmed as 3rd project,
                                     #        DietSense deferred, blockers/implementaton plan revised
```

### Files NOT modified (existing repos — Phase 0 rule)

No files in `campus-guardian/`, `diet-sense/`, or `friday/` were changed.

---

## Key implementation decisions

### 1. LLM adapter — abstract from day one
The `LLMAdapter` abstract base class defines the interface any provider must implement. The `register_provider` decorator pattern means new providers can be added without touching the orchestration code. Phase 5 will implement OpenAI/Anthropic/Ollama adapters.

### 2. Connector result typing
`ConnectorResult` is a dataclass with `project_id`, `status` (healthy/degraded/unavailable/unknown), `checked_at`, `latency_ms`, `data`, and `error`. Every connector call returns this shape — the orchestration layer never sees raw HTTP responses or exceptions from upstream projects.

### 3. Permission model
Three levels: READ (no confirmation), CONTROLLED (confirmation required), RESTRICTED (confirmation required + stronger authorization). The `require_permission()` function is called on every tool execution. The chat endpoint requests approval *before* checking permissions for confirmation-requiring actions, so a RESTRICTED action goes to the approval flow first.

### 4. Intent matching (Phase 1 stopgap)
Keyword-based pattern matching in `routes_chat.py`. Replaced by LLM intent routing in Phase 5. Patterns are ordered so specific actions ("remove", "add source") are checked before generic nouns ("source", "incident").

### 5. Campus Guardian connector
All 10 tools map directly to verified endpoints from Phase 0. The connector uses `BaseHTTPConnector` which handles HTTP calls, timeout, and error mapping. The `cg_get_snapshot` and `cg_get_clip` tools return binary endpoints — the IASA API layer (Phase 6) will proxy these as base64 in chat responses.

### 6. F.R.I.D.A.Y connector
Connects to the hub as a WebSocket client. Implements the full HANDSHAKE → AUTH → execute flow. The `friday_health` tool uses the same `health()` method (not just `execute()`). The connector does **not** require the Flutter client apps (which are empty stubs) — it talks directly to the hub.

### 7. Database — PostgreSQL-ready from the start
Models use `sqlalchemy.Uuid` (generic, works with SQLite in dev and PostgreSQL in prod). No SQLite-specific code in the model layer. Alembic migrations will be added in Phase 2.

---

## Test results (7/7 passing)

| # | Test | Expected | Actual | Result |
|---|------|----------|--------|--------|
| 1 | `GET /api/health` | `degraded` (both projects unavailable in test env) | `degraded` — CG: unavailable (port 9999 not running), FRIDAY: unavailable (no session key) | ✅ |
| 2 | `GET /api/tools` | 14 tools (10 CG + 4 FRIDAY) | 14 tools, correct permissions and confirmation flags | ✅ |
| 3 | Chat: "check campus guardian health" | → `cg_health` executed | Tool matched, executed, result `unavailable` (CG not running) | ✅ |
| 4 | Chat: "remove camera source" | → APPROVAL REQUIRED for `cg_remove_source` (RESTRICTED) | Approval returned with correct tool, permission, project, description | ✅ |
| 5 | Chat: "friday hub status" | → `friday_health` executed | Tool matched, executed, result `unavailable` (no session key) | ✅ |
| 6 | Chat: "show me recent incidents" | → `cg_list_incidents` | Tool matched and executed | ✅ |
| 7 | Chat: "hello what can you do" | → help text, no tools | Help text listing all 14 tools returned | ✅ |

---

## What's working end-to-end

```
User message  →  intent match (keyword)  →  tool lookup  →  permission check
                                                      →  approval request (if needed)
                                                      →  connector.execute()  →  ConnectorResult
                                                                              →  formatted response
```

Example: `"remove camera source"` →
- Match: `cg_remove_source` (RESTRICTED, requires_confirmation=True)
- Returns: `approval_required=True`, `approval_request={tool_name, action_description, permission, project_id, ...}`
- The frontend (Phase 6) will render an approval dialog; on confirm, call `POST /api/tools/execute`

---

## Known limitations (Phase 1 — honest, not blocking)

| # | Limitation | When resolved |
|---|------------|---------------|
| L-1 | No real LLM call yet — keyword matching only | Phase 5 (LLM orchestration) |
| L-2 | No user auth / JWT — `user_id` is a stub parameter | Phase 2 (auth skeleton) |
| L-3 | No database migrations (Alembic) run yet — models defined but no tables created | Phase 2 |
| L-4 | Campus Guardian not running in test environment — all CG tools return `unavailable` | Run CG on its port and set `CG_API_BASE_URL` |
| L-5 | F.R.I.D.A.Y hub not running — no `SESSION_KEY` configured | Run hub with `SESSION_KEY` and set `FRIDAY_HUB_SESSION_KEY` |
| L-6 | DietSense integration deferred — project is in working phase | Revisit when DietSense backend is available |
| L-7 | Binary endpoints (snapshot/clip) return a note, not actual base64 — IASA API layer needed | Phase 6 frontend |
| L-8 | No WebSocket for IASA chat status — Phase 6 | Phase 6 |

---

## How to run locally

```bash
cd ~/Developer/IASA/backend

# 1. Create virtual environment (one time)
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure .env (copy .env.example and fill in)
#    At minimum set DATABASE_URL for your DB

# 4. Run the server
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 5. Test
curl http://localhost:8000/api/health
curl http://localhost:8000/api/tools
curl -X POST http://localhost:8000/api/chat -H "Content-Type: application/json" \
  -d '{"message":"check campus guardian health","user_id":"demo"}'
```

---

## Next phase: Phase 2

Phase 2 will add:
- Alembic migrations + database initialization
- User/auth skeleton (JWT, user model, workspace membership)
- Wire the CG connector to a running Campus Guardian instance
- Wire the F.R.I.D.A.Y connector to a running hub
- Chat UI scaffold (frontend)
- Tool execution from chat (when no approval needed)
- Approval flow UI (frontend)

**Before Phase 2, user needs to:**
1. Run Campus Guardian on its port and set `CG_API_BASE_URL` in IASA `.env`
2. Run F.R.I.D.A.Y hub with a known `SESSION_KEY` and set `FRIDAY_HUB_SESSION_KEY` in IASA `.env`
3. Decide on LLM provider (or keep keyword matching until Phase 5)

---

*Phase 1 complete. No code changes to existing repos. Backend running and verified.*
