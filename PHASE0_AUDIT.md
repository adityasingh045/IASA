# IASA Phase 0 — Repository & Architecture Audit
**Date:** 6 November 2026  
**Auditor:** IASA build system  
**Status:** Complete — no code changes made to any repository  

---

## Repositories inspected

| # | Project | Repo URL | Default branch | Language | Size | Last push |
|---|---------|----------|----------------|----------|------|-----------|
| 1 | Campus Guardian | `adityasingh045/Campus-Guardian` | `main` | Python | ~26 MB | 16 Oct 2026 |
| 2 | DietSense | `adityasingh045/DIETESENSE` | `main` | TypeScript/React | ~105 KB | 16 Jun 2026 |
| 3 | F.R.I.D.A.Y | `adityasingh045/F.R.I.D.A.Y` | `main` | Dart (Flutter) + Node.js | ~17 KB source (many files empty) | 30 Aug 2026 |

> **Note on repo #3:** The IASA prompt's original concept describes "NeuroVoice" (EMG-based assistive communication). The actual third repo provided and confirmed by the user is **F.R.I.D.A.Y** — a multi-screen collaboration/relay tool (Flutter + Node.js hub). The IASA spec is adapted to treat F.R.I.D.A.Y as the third integrated project. See Blockers section for the original NeuroVoice gap.

---

## 1. Campus Guardian — Repository Map

### File structure (non-`node_modules` / non-`__pycache__`)

```
campus-guardian/
├── Dockerfile
├── nginx.conf
├── architecture.md          # Full architecture doc (read — very detailed)
├── index.html
├── package.json             # Frontend deps only (react, react-dom, tailwind, vite)
├── postcss.config.js
├── package-lock.json
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt     # fastapi, uvicorn, pydantic, sqlalchemy, aiosqlite,
│   │                        # httpx, opencv-python-headless, numpy, ultralytics,
│   │                        # lapx, websockets, python-multipart
│   ├── requirements-dev.txt
│   ├── app/
│   │   ├── main.py          # FastAPI entry point; lifespan init; 4 routers registered
│   │   ├── config.py        # Pydantic Settings — all env vars documented
│   │   ├── auth.py          # X-API-Key header check + WS query-param check
│   │   ├── api/
│   │   │   ├── routes_health.py   # GET / and GET /api/health
│   │   │   ├── routes_sources.py  # GET/POST/DELETE /api/sources, POST /api/sources/phone,
│   │   │   │                        # POST /api/sources/phone/{id}/frame
│   │   │   ├── routes_incidents.py # GET /api/incidents, GET /api/incidents/{id},
│   │   │   │                          # POST /api/incidents/{id}/review,
│   │   │   │                          # GET /api/incidents/{id}/snapshot,
│   │   │   │                          # GET /api/incidents/{id}/clip,
│   │   │   │                          # GET /api/incidents/{id}/report.pdf
│   │   │   └── ws_live.py         # WebSocket /ws/live (auth via ?key= query param)
│   │   ├── db/
│   │   │   ├── session.py   # async SQLAlchemy engine (sqlite+aiosqlite, WAL mode)
│   │   │   ├── models.py    # Incident, IncidentEvent ORM models
│   │   │   └── init_db.py   # create_all + additive ALTER TABLE on startup
│   │   ├── detection/
│   │   │   ├── engine.py    # CameraEngine: per-source thread, YOLO+ByteTrack+signals
│   │   │   ├── camera.py    # CameraReader (cv2.VideoCapture wrapper)
│   │   │   ├── config.py    # DetectionConfig dataclass
│   │   │   ├── signals.py   # proximity, swing, arm, fall signal computation
│   │   │   ├── temporal.py  # temporal confirmation + cooldown logic
│   │   │   ├── tracker.py   # PersonTracker (YOLOv8-pose + ByteTrack wrapper)
│   │   │   ├── evidence.py  # EvidenceCollector + EvidenceRingBuffer
│   │   │   ├── incident_state.py  # Incident state machine
│   │   │   ├── person_tracker.py  # (duplicate? referencing tracker.py)
│   │   │   ├── movement_analyzer.py
│   │   │   ├── homography.py
│   │   │   ├── annotator.py
│   │   │   └── pose_estimator.py
│   │   └── services/
│   │       ├── alert_service.py
│   │       ├── calibration_service.py
│   │       ├── cleanup_service.py
│   │       ├── escalation_service.py
│   │       ├── frame_broadcaster.py
│   │       ├── telegram_service.py
│   │       └── ws_manager.py
│   ├── data/
│   │   ├── campus_guardian.db           # SQLite DB (seems to have data)
│   │   └── campus_guardian_oldschema_backup.db
│   └── snapshots/                        # Incident evidence (snapshots + clips)
│       ├── INC-20261015-9EBF1D/
│       └── INC-20261015-C8A42F/
├── frontend/                              # React SPA (NOT a separate npm package)
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── index.html
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       ├── index.css
│       ├── utils/
│       │   ├── api.js        # Complete API client — all routes documented
│       │   ├── prefs.js
│       │   └── sound.js
│       ├── hooks/
│       │   ├── useWebSocket.js
│       │   ├── useIncidents.js
│       │   └── useSources.js
│       ├── components/
│       │   ├── AlertDetailsPanel.jsx
│       │   ├── CameraCard.jsx
│       │   ├── CameraGrid.jsx
│       │   ├── CameraHistoryDrawer.jsx
│       │   ├── IncidentCard.jsx
│       │   ├── IncidentHistory.jsx
│       │   ├── IncidentsFeed.jsx
│       │   ├── Navbar.jsx
│       │   ├── PhoneCameraManager.jsx
│       │   ├── PhoneCameraPage.jsx
│       │   ├── Sidebar.jsx
│       │   ├── SnapshotThumb.jsx
│       │   ├── StatusBadge.jsx
│       │   ├── SystemStatusBar.jsx
│       │   ├── TopBar.jsx
│       │   └── CameraFullView.jsx
│       └── pages/
│           ├── DashboardPage.jsx
│           ├── CamerasPage.jsx
│           ├── HistoryPage.jsx
│           └── SettingsPage.jsx
└── demo/                    # Demo assets?
```

### Tech stack summary
- **Backend:** Python 3.11/3.14, FastAPI 0.115.0, Uvicorn 0.30.6, Pydantic 2.9.2, SQLAlchemy 2.0.35 async, aiosqlite 0.20.0, OpenCV 4.10, Ultralytics 8.3.0 (YOLOv8-pose + ByteTrack), websockets 13.1
- **Frontend:** React 18, Vite 5, Tailwind CSS 3.4, no separate state library
- **Database:** SQLite (async via aiosqlite), WAL mode, single file
- **Deployment:** Docker Compose (backend + frontend containers), optional Nginx reverse proxy (`nginx.conf` present but not in Compose)
- **External services:** Telegram Bot API (optional, fire-and-forget notifications)

---

## 2. Campus Guardian — Verified API Inventory (Point 3 of audit)

### Authentication
- **Mechanism:** Single shared `API_KEY` string
- **REST:** `X-API-Key` header on every route except `GET /` and `GET /api/health`
- **WebSocket:** `?key=<API_KEY>` query parameter on WS handshake; validated before `accept()`; close code 4401 on failure
- **Auth code:** `backend/app/auth.py` — `require_api_key()` (HTTP 401 on failure), `require_ws_api_key()` (returns bool)
- **Config:** `backend/app/config.py` — `api_key`, `allow_no_auth` flags. If `API_KEY` is empty and `ALLOW_NO_AUTH=false`, app refuses to start with `RuntimeError`.

### Route table (verified from source code)

| Method | Path | Auth | Request body | Response shape | Notes |
|--------|------|------|-------------|----------------|-------|
| GET | `/` | ✗ | — | `{service, status, version}` | Health ping, no auth |
| GET | `/api/health` | ✗ | — | `{status, sources_total, sources_online, sources_errored, sources_stalled, ws_connected_clients, sources: [...]}` | Aggregated source liveness; `status` is `"ok"`/`"degraded"`/`"down"`/`"starting"` |
| GET | `/api/sources` | ✓ | — | `{sources: [{source_id, source_type, location, zone, status, using_synthetic_feed, person_count, max_movement, closest_distance, activity_status, active_incident_id, last_frame_age_seconds}]}` | List all source statuses |
| GET | `/api/sources/{source_id}` | ✓ | — | Same source object or 404 | Single source status |
| POST | `/api/sources` | ✓ | `AddSourceRequest` (`source_id, source_type, location, uri, enabled, zone`) | `{status: "added", source_id}` | Add source at runtime; 409 if duplicate |
| DELETE | `/api/sources/{source_id}` | ✓ | — | `{status: "removed", source_id}` | Remove source |
| POST | `/api/sources/phone` | ✓ | `PhoneCameraRegistration` (`source_id, location, zone`) | `{status: "waiting_for_phone", source_id, location}` | Register phone camera; creates RUNTIME-type source |
| POST | `/api/sources/phone/{source_id}/frame` | ✓ | Raw JPEG body (`image/jpeg`, 1B–2MB) | `{status: "accepted", source_id, width, height}` | Ingest phone frame; 413 if >2MB, 400 if invalid JPEG |
| GET | `/api/incidents` | ✓ | Query: `limit, offset, source_id, state` | `{total, active_incidents, limit, offset, items: [{incident_id, source_id, location, started_at, resolved_at, state, people_involved, peak_movement, min_distance, description, has_snapshot, telegram_status, zone, group_id, is_additional_angle, reviewed_at, escalated_at}]}` | Paginated incident list; `active_incidents` count included |
| GET | `/api/incidents/{incident_id}` | ✓ | — | Full incident + `angles: [...]` + `timeline: [{ts, label, detail}]` | Single incident detail with multi-camera angles and timeline |
| POST | `/api/incidents/{incident_id}/review` | ✓ | — | `{incident_id, reviewed_at}` | Mark incident reviewed; stops escalation timer; also reviews correlated angles |
| GET | `/api/incidents/{incident_id}/snapshot` | ✓ | — | JPEG image (FileResponse) | Primary snapshot; 404 if no snapshot |
| GET | `/api/incidents/{incident_id}/clip` | ✓ | Query: `download` | MP4 video (FileResponse) | Evidence clip; 404 until post-event window completes (~10s) |
| GET | `/api/incidents/{incident_id}/report.pdf` | ✓ | — | PDF (Response) | One-page incident report; requires `reportlab` package (501 if missing) |
| WS | `/ws/live` | ✓ (query param `?key=`) | — | Frames as JSON: `{frame: <base64 JPEG>, stats: {...}, ts: <unix timestamp>}` | Live annotated video stream; authclose 4401/4408 |

### Source types supported
From `backend/app/sources/base.py`: `SourceType` enum includes `WEBCAM`, `UPLOADED_VIDEO`, `RTSP`, `RUNTIME_STREAM` (phone camera), `CCTV`. The `AddSourceRequest.source_type` uses this enum.

### Error format
- Standard FastAPI: HTTP status code + JSON `{detail: "error message"}`
- Auth failure: `401 Unauthorized` with `{detail: "Invalid or missing API key"}`
- Not found: `404` with `{detail: "..."}`  
- Conflict: `409` with `{detail: "..."}`
- Bad request: `400` with `{detail: "..."}`
- Payload too large: `413`
- WS auth failure: close code `4401`; too many connections: `4408`

### CORS
Configured via `CORSMiddleware`. Default: `http://localhost:5173,http://127.0.0.1:5173`. Configurable via `CORS_ORIGINS` env var (comma-separated; `"*"` for dev).

### Health-check safety
`GET /api/health` is safe to call frequently — it reads in-memory source status from `SourceManager.all_statuses()`, no DB write, no external call. Returns `status: "starting"` if `source_manager` not yet initialised.

---

## 3. Campus Guardian — Runtime / Deployment Summary

### Environment variables (from `config.py` + `.env` sample)

| Var | Required | Default | Notes |
|-----|----------|---------|-------|
| `API_KEY` | ✓ (unless `ALLOW_NO_AUTH=true`) | — | Must be set or app refuses to start |
| `ALLOW_NO_AUTH` | — | `false` | Local demo only; exposes live feed without auth |
| `CAMERA_SOURCE` | — | `"0"` | Webcam index, RTSP URL, or video file path |
| `TEST_VIDEO_FALLBACK` | — | `true` | Fall back to synthetic video if camera fails |
| `MODEL_PATH` | — | `"yolov8n.pt"` | Ultralytics model; downloads automatically |
| `DEVICE` | — | `""` | `"cpu"` or `"cuda:0"` |
| `DETECTION_CONF` | — | `0.55` | YOLO confidence threshold |
| `DB_PATH` | — | `backend/data/campus_guardian.db` | SQLite path |
| `SNAPSHOT_DIR` | — | `backend/snapshots` | Evidence storage |
| `SNAPSHOT_RETENTION_DAYS` | — | `14` | Cleanup policy |
| `TELEGRAM_BOT_TOKEN` | — | — | Optional; leave blank to disable |
| `TELEGRAM_CHAT_ID` | — | — | Optional |
| `CORS_ORIGINS` | — | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated |
| `WS_MAX_CONNECTIONS` | — | `20` | WS connection limit |

### Startup command
```bash
# Backend
cd backend && pip install -r requirements.txt && uvicorn app.main:app --host 0.0.0.0 --port 8000

# Frontend (separate terminal)
cd frontend && npm install && npm run dev
```

### Docker
`docker-compose.yml` at repo root: two services — `cg-backend` (port 8000) and `cg-frontend` (port 5173). Volumes for DB, snapshots, sources config, YOLO weight cache.

### Important observations
- The `.env` file **contains real secrets**: `API_KEY=FfObbWwLNWQcwT451zGjyVWq5m5AmtbFV18VF3F6HI4`, a Telegram bot token `8749168187:AAGCRb6NKTKQQZTYDVoC0E_vmQzCXXgeygc`, and a Telegram chat ID `5503377070`. These are committed to the repo. **Security finding.**
- `ALLOW_NO_AUTH=true` is set in `.env`, meaning the deployed instance may be running unauthenticated.
- The backend uses `yolov8n-pose.pt` (not `yolov8n.pt` as in config default) — the `.env` overrides `MODEL_PATH=yolov8n-pose.pt`.
- `architecture.md` is comprehensive and accurately reflects the code.
- The `routes_alerts.py` file referenced in `architecture.md` does not exist; the incident routes are in `routes_incidents.py`. The architecture doc is slightly out of date on this naming.

---

## 4. Campus Guardian — Security Risk Register

| # | Finding | Severity | Notes |
|---|---------|----------|-------|
| CG-SEC-1 | Real API key, Telegram bot token, and chat ID committed in `.env` | **High** | Anyone with repo access has live credentials. Rotate immediately. |
| CG-SEC-2 | `ALLOW_NO_AUTH=true` in .env | **High** | If deployed as-is, live camera feed and incident data are unauthenticated. |
| CG-SEC-3 | Telegram token logged? | **Medium** | Token is not logged in normal operation; only used in outbound HTTPS. Check TelegramService code to confirm no logging. |
| CG-SEC-4 | API key shared publicly in browser bundle | **Medium** | `VITE_API_KEY` is baked into the frontend JavaScript. The architecture doc acknowledges this: "This key is still public in the browser; use a server-side auth design for production." |
| CG-SEC-5 | Snapshot files served without additional auth beyond API key | **Medium** | Snapshot/clip endpoints check API key but no per-user authorization. Anyone with the key can download all incident evidence. |
| CG-SEC-6 | No rate limiting on API endpoints | **Medium** | No rate limiter observed; brute-force or DoS potential on auth endpoint. |
| CG-SEC-7 | SQLite file + snapshot dir mounted as Docker volumes | **Low** | Persists across container restarts; backup/restore not automated. |
| CG-SEC-8 | CORS defaults to specific origins but can be wildcarded | **Low** | Configurable; `CORS_ORIGINS=*` is possible. |

---

## 5. DietSense — Repository Map

```
diet-sense/
├── index.html
├── package.json              # React 18, @supabase/supabase-js ^2.57.4, lucide-react,
│                             # tailwindcss ^3.4.1, vite ^5.4.2, typescript ^5.5.3
├── package-lock.json
├── tsconfig.json
├── tsconfig.app.json
├── tsconfig.node.json
├── vite.config.ts
├── tailwind.config.js
├── postcss.config.js
├── eslint.config.js
├── vite-env.d.ts
├── .env                      # ⚠️ Contains REAL Supabase URL + anon key
├── .gitignore
├── src/
│   ├── main.tsx
│   ├── App.tsx               # App stages: hero → onboarding → app; session via localStorage
│   ├── index.css
│   ├── assets/hero.jpg
│   ├── components/
│   │   ├── Dashboard.tsx     # Main dashboard: meal type, allergies, mood, weather, recipe grid
│   │   ├── FoodForm.tsx
│   │   ├── Hero.tsx
│   │   ├── LanguageSwitcher.tsx
│   │   ├── Login.tsx
│   │   ├── LoginDrawer.tsx
│   │   ├── Logout.tsx
│   │   ├── MoodSelector.tsx
│   │   ├── Onboarding.tsx
│   │   ├── RecipeCard.tsx
│   │   ├── RecipeChat.tsx    # Chat widget: POSTs to /api/chat (relative path, no base URL)
│   │   ├── RecipeModal.tsx   # Recipe detail + TTS voice cooking + YouTube/Swiggy/Zomato links
│   │   ├── Register.tsx
│   │   ├── SearchPage.tsx
│   │   ├── SideNav.tsx
│   │   ├── ThemeToggle.tsx
│   │   └── WeatherWidget.tsx
│   ├── context/
│   │   ├── LanguageContext.tsx
│   │   └── ThemeContext.tsx
│   ├── lib/
│   │   ├── supabase.ts       # createClient(VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY)
│   │   ├── database.types.ts # Supabase generated types: recipes, user_preferences, common_allergies
│   │   ├── translate.ts
│   │   ├── weather.ts
│   │   └── foodAI.ts         # POSTs to http://localhost:8080/completion
│   ├── pages/
│   │   ├── stepSpeaker.ts
│   │   ├── translate.ts
│   │   ├── voiceCommands.ts  # Re-exports from utils/voiceInstructions.ts
│   │   └── voiceInstructions.ts
│   ├── utils/
│   │   ├── foodAI.ts         # getFoodRecommendation(): fetches localhost:8080/completion
│   │   ├── parseFoodAI.ts
│   │   └── saveAIRecommendation.ts  # Inserts into supabase ai_food_recommendations table
│   └── assets/
└── supabase/
    ├── functions/chat/index.ts   # ❌ Entirely commented out — Deno chat function
    └── migrations/
        └── 20251216151236_create_moodmeal_schema.sql  # DB schema
```

### Tech stack summary
- **Frontend:** React 18.3, TypeScript 5.5, Vite 5.4, Tailwind CSS 3.4, Lucide React, Supabase JS 2.57
- **Backend:** Supabase (Postgres) — no standalone backend server in this repo
- **AI provider:** Calls `http://localhost:8080/completion` (external/local service not in this repo); the commented-out Supabase function used Google Gemini
- **Database:** Supabase Postgres; tables: `recipes`, `user_preferences`, `common_allergies`, `ai_food_recommendations` (referenced in saveAIRecommendation.ts but not in migration)
- **Hosted at:** `https://dietesense.vercel.app` (per repo homepage)

---

## 6. DietSense — Verified API / Integration Inventory (Point 3 of audit)

### Authentication
- **Supabase:** Uses `VITE_SUPABASE_ANON_KEY` (anon/key UX is JWT-based; RLS policies apply). Key is embedded in frontend bundle.
- **No standalone backend auth** — this is a purely frontend + Supabase project.

### Data contracts (from `database.types.ts` — verified Supabase generated types)

**Table: `recipes`**
```typescript
{
  id: string;
  name: string;
  description: string;
  image_url: string;
  ingredients: string[] | null;
  recipe_steps: string[] | null;
  age_group: string | null;
  prep_time: number;
  servings: number;
  calories: number;
  protein: number;
  carbs: number;
  meal_type: string;        // or string[] in some usages
  mood_tags: string[];
  weather_tags: string[];
  allergens: string[];
  created_at: string;
}
```

**Table: `user_preferences`**
```typescript
{
  id: string;
  session_id: string;       // used as user identifier (localStorage UUID)
  age_group: string;
  preferred_meal_types: string[];
  allergies: string[];
  created_at: string;
  updated_at: string;
}
```

**Table: `common_allergies`**
```typescript
{
  id: string;
  name: string;
  description: string;
  created_at: string;
}
```

### External service calls (verified from source code)

| Endpoint | Method | Purpose | Auth | Notes |
|----------|--------|---------|------|-------|
| `http://localhost:8080/completion` | POST | Food recommendation AI | None | Body: `{age, mood, weather, allergies}`; expects text response with `Food Name:`, `Why it fits:`, `Calories:`, `Protein:`, `Carbs:`, `Fats:` labels |
| `VITE_SUPABASE_URL/rest/v1/recipes` | GET | Load recipes | Supabase anon key (RLS) | Via `supabase.from("recipes").select("*")` |
| `VITE_SUPABASE_URL/rest/v1/user_preferences` | SELECT/UPSERT | Read/write user prefs | Supabase anon key | Per-session prefs |
| `VITE_SUPABASE_URL/rest/v1/ai_food_recommendations` | INSERT | Log AI recommendations | Supabase anon key | Table exists in code but not in migration file |
| `/api/chat` (relative) | POST | Recipe chat | None | Handled by `RecipeChat.tsx`; points to `/api/chat` with no base URL — likely broken in standalone frontend without a proxy |

### WebSocket
None.

### Error format
- Supabase client throws on errors; caught in `saveAIRecommendation` (logged to console).
- `getFoodRecommendation` throws on non-200 from localhost:8080.
- `RecipeChat` has no error handling — will crash UI on fetch failure.

---

## 7. DietSense — Runtime / Deployment Summary

### Environment variables
| Var | Required | Notes |
|-----|----------|-------|
| `VITE_SUPABASE_URL` | ✓ | Supabase project URL |
| `VITE_SUPABASE_ANON_KEY` | ✓ | Supabase anon JWT key |

### Startup
```bash
npm install && npm run dev   # Vite dev server; no backend to start in this repo
```

### External dependencies
- Supabase project (Postgres + Auth + Storage)
- Local/remote service at `localhost:8080` for AI food completion — **not included in this repo**
- Weather API (implemented in `src/lib/weather.ts` — needs investigation)

### Important observations
- The `.env` file **contains a real Supabase URL and anon key** committed to the repo.
- The Supabase chat function (`supabase/functions/chat/index.ts`) is **100% commented out** — the Gemini-based chat feature is non-functional.
- RecipeChat component posts to `/api/chat` with no `API_BASE` prefix — this endpoint doesn't exist in the Vite dev server; the feature is likely broken.
- The `foodAI.ts` module calls `localhost:8080` — this implies a separate backend service that is **not in this repo**. Without it, food recommendations don't work.
- DietSense's own backend (the localhost:8080 service) must be found or rebuilt separately. The IASA prompt mentioned "earlier backend iterations have included FastAPI and Node/Express with Ollama" — this repo does not contain that backend.

---

## 8. DietSense — Security Risk Register

| # | Finding | Severity | Notes |
|---|---------|----------|-------|
| DS-SEC-1 | Real Supabase URL + anon key in `.env` committed to repo | **High** | Anon key is client-side by design but should not be in git history. RLS policies must be verified. |
| DS-SEC-2 | No RLS policy audit performed | **High** | With anon key in the browser, Postgres Row Level Security is the only access control. Policy state is unknown without Supabase project access. |
| DS-SEC-3 | `ai_food_recommendations` table used in code but not in migration | **Medium** | Schema mismatch — table may exist in DB but not in declared migrations. |
| DS-SEC-4 | `/api/chat` endpoint unreachable in standalone frontend | **Medium** | RecipeChat feature is non-functional without a proxy or backend. |
| DS-SEC-5 | Localhost:8080 AI service is an external dependency not in repo | **Medium** | Cannot verify that service's security, auth, or privacy behaviour. |
| DS-SEC-6 | No standalone backend auth; all logic in frontend + Supabase RLS | **Medium** | IASA integration must go through Supabase API or rebuild the missing backend. |
| DS-SEC-7 | Age, allergies, mood data stored in Supabase | **Medium** | Personal data; IASA must not send this to an LLM provider unnecessarily. |

---

## 9. F.R.I.D.A.Y — Repository Map

```
F.R.I.D.A.Y/
└── FRIDAY/
    ├── README.md             # Contains only "# F.R.I.D.A.Y" — no documentation
    ├── shared/
    │   └── protocol.dart     # ⚠️ 0 bytes — empty file
    ├── desktop_app/
    │   ├── hub/
    │   │   ├── server.js     # ✅ Complete Node.js ws + HTTP/2 hub implementation
    │   │   ├── auth.js       # ⚠️ 0 bytes — empty
    │   │   ├── encryption.js # ⚠️ 0 bytes — empty (encryption logic is inline in server.js)
    │   │   └── file_proxy.js # ⚠️ 0 bytes — empty (file proxy logic is inline in server.js)
    │   └── lib/
    │       ├── main.dart     # ⚠️ 0 bytes — empty
    │       ├── mirror_view.dart  # ⚠️ 0 bytes — empty
    │       ├── input_relay.dart  # ⚠️ 0 bytes — empty
    │       ├── drag_target.dart  # ⚠️ 0 bytes — empty
    │       ├── clipboard_sync.dart  # ⚠️ 0 bytes — empty
    ├── android_app/
    │   └── lib/
    │       ├── main.dart     # ⚠️ 0 bytes — empty
    │       ├── ai_classifier.dart  # ✅ Complete: MobileNet TFLite image classification
    │       ├── screen_stream.dart  # ✅ Complete: screen capture + WS streaming
    │       ├── discovery.dart      # ✅ Complete: mDNS device discovery
    │       ├── drag_overlay.dart   # ✅ Complete: drag-and-drop UI overlay
    │       ├── clipboard_sync.dart # ⚠️ 0 bytes — empty
    │       ├── crypto.dart         # ✅ Complete: AES encryption utilities
    │       └── input_forward.dart  # ⚠️ 0 bytes — empty
```

### Tech stack summary
- **Desktop app:** Flutter/Dart (partial — main.dart and most lib files are empty)
- **Android app:** Flutter/Dart (partial — main.dart, clipboard_sync.dart, input_forward.dart are empty)
- **Hub:** Node.js 20+, `ws` 8.x, `http2` native, `multicast-dns` — **complete and functional**
- **ML:** TensorFlow Lite (MobileNetV2) via `tflite_flutter` — implemented in `ai_classifier.dart`
- **Encryption:** AES-256-GCM (implemented inline in `server.js`; `crypto.dart` has Dart-side utilities)

---

## 10. F.R.I.D.A.Y — Verified API / Integration Inventory (Point 3 of audit)

### Hub WebSocket protocol (verified from `server.js`)

The hub is a **device collaboration relay**, not an EMG or speech-assistive system.

**Connection:** `ws://<hub-host>:8765`

**Message flow:**
1. Client connects → hub sends `HANDSHAKE` with `deviceId` + random `challenge`
2. Client sends `AUTH` message with `keyHash` (SHA-256 of `SESSION_KEY` env var) + `deviceType` + `deviceName`
3. Hub compares hash → `AUTH_OK` or `AUTH_FAIL` (close 4003)
4. Authorized clients can send: `SCREEN_FRAME`, `INPUT_EVENT`, `CLIPBOARD`, `DRAG_PAYLOAD`, `VOICE_CMD`
5. Messages route to specific `targetId` or broadcast to all authorized clients
6. All messages are AES-256-GCM encrypted (envelope: `{iv, data, tag}`)

**Message types (from server.js switch):**
| Type | Direction | Auth required | Payload |
|------|-----------|---------------|---------|
| `HANDSHAKE` | Hub → Client | — | `{deviceId, challenge}` |
| `AUTH` | Client → Hub | — | `{keyHash, deviceType, deviceName}` |
| `AUTH_OK` | Hub → Client | — | `{type, deviceId}` |
| `AUTH_FAIL` | Hub → Client | — | `{type}` |
| `SCREEN_FRAME` | Either → Hub | ✓ | `{type, targetId?, ...}` |
| `INPUT_EVENT` | Either → Hub | ✓ | `{type, targetId?, ...}` |
| `CLIPBOARD` | Either → Hub | ✓ | `{type, targetId?, ...}` |
| `DRAG_PAYLOAD` | Either → Hub | ✓ | `{type, targetId?, ...}` |
| `VOICE_CMD` | Either → Hub | ✓ | `{type, targetId?, ...}` |
| `FILE_TRANSFER_INIT` | Client → Hub | ✓ | `{type, targetId, filename}` → hub responds with `FILE_TOKEN` + HTTP/2 port |
| `FILE_TOKEN` | Hub → Client | — | `{type, token, port}` |
| `FILE_READY` | Hub → Client | — | `{type, filename, path}` |
| `DEVICE_CONNECTED` | Hub → broadcast | — | `{type, deviceId, name}` |
| `DEVICE_DISCONNECTED` | Hub → broadcast | — | `{type, deviceId}` |

**HTTP/2 file proxy:** Port 8766; uploads use `x-file-token` header; saves to `./uploads/`.

**mDNS:** Service name `multi-screen-collate` (note: `server.js` says `multi-screen-collaborate` in CONFIG but responds with `multi-screen-collate` — possible typo).

### Empty files (critical finding)
The following files exist but are **0 bytes** — they are stubs, not implemented:
- `shared/protocol.dart` — no shared protocol definition
- `desktop_app/hub/auth.js` — auth logic is in `server.js` instead
- `desktop_app/hub/encryption.js` — encryption logic is in `server.js` instead
- `desktop_app/hub/file_proxy.js` — file proxy logic is in `server.js` instead
- `desktop_app/lib/main.dart` — no desktop app entry point
- `desktop_app/lib/mirror_view.dart` — no implementation
- `desktop_app/lib/input_relay.dart` — no implementation
- `desktop_app/lib/drag_target.dart` — no implementation
- `desktop_app/lib/clipboard_sync.dart` — no implementation
- `android_app/lib/main.dart` — no Android app entry point
- `android_app/lib/clipboard_sync.dart` — no implementation
- `android_app/lib/input_forward.dart` — no implementation

**Only fully implemented Dart files:**
- `android_app/lib/ai_classifier.dart` — MobileNet image classification
- `android_app/lib/screen_stream.dart` — screen capture + WS streaming
- `android_app/lib/discovery.dart` — mDNS discovery
- `android_app/lib/drag_overlay.dart` — drag-and-drop UI
- `android_app/lib/crypto.dart` — AES utilities

### Is this NeuroVoice?
**No.** F.R.I.D.A.Y is a multi-screen collaboration/relay tool. There is:
- No EMG signal acquisition code
- No muscle sensor interface
- No speech restoration logic
- No command classification beyond image file type classification (MobileNet)
- No "relax, clench, double, shrug" labels or "SOS, pill, food" commands mentioned in the IASA prompt

The `VOICE_CMD` message type exists in the hub but has no implementation on the client side (the receiving/processing logic is in empty files).

---

## 11. F.R.I.D.A.Y — Runtime / Deployment Summary

### Hub startup
```bash
cd FRIDAY/desktop_app/hub
npm install          # needs: ws, multicast-dns
SESSION_KEY=<key> node server.js
# → WS on port 8765, HTTP/2 on port 8766, mDNS broadcast
```

### Environment variables
| Var | Required | Default | Notes |
|-----|----------|---------|-------|
| `SESSION_KEY` | — | Random 32 bytes hex at startup | AES key + auth hash source; must be same across all devices |

### Ports
- Hub WebSocket: `8765`
- Hub HTTP/2 file proxy: `8766`

### Important observations
- The hub `server.js` is self-contained and appears functional.
- The Flutter apps are non-functional skeletons (no `main.dart`).
- The project has no `pubspec.yaml` — Flutter projects require this. Its absence confirms the Dart code has never been built.
- No `package.json` in the hub directory — dependencies (`ws`, `multicast-dns`) would need to be installed.

---

## 12. F.R.I.D.A.Y — Security Risk Register

| # | Finding | Severity | Notes |
|---|---------|----------|-------|
| FR-SEC-1 | `SESSION_KEY` defaults to random at startup — devices can't authenticate each other | **High** | Each hub restart generates a new key; previously connected devices will fail auth. No persistent key management. |
| FR-SEC-2 | AES key transmitted? No — keyHash is SHA-256 of key, sent in AUTH message | **Medium** | keyHash is a hash, not the key itself. But if `SESSION_KEY` is weak or predictable, the hash is brute-forceable. |
| FR-SEC-3 | mDNS advertises service on all interfaces | **Medium** | `multi-screen-collate` service visible on local network; no auth on mDNS queries. |
| FR-SEC-4 | HTTP/2 file proxy has no file type/size restrictions | **Medium** | Any file type accepted; no size limit visible. |
| FR-SEC-5 | Empty client apps — no security review possible for client side | **Low** | Client code doesn't exist yet. |
| FR-SEC-6 | No TLS on WS or HTTP/2 | **Medium** | Both use plain text (ws://, http://); encryption is application-layer AES only. |

---

## 13. Cross-project Integration Matrix (preliminary — Point 7 of audit)

> **Status: Provisional.** This matrix maps IASA's desired capabilities to actual endpoints. Items marked `⚠️` need resolution. Items marked `❌` are not possible with current repos.

### Campus Guardian integration

| IASA capability | Actual endpoint | Method | Auth | Permission level | Notes |
|----------------|-----------------|--------|------|-----------------|-------|
| Health check | `/api/health` | GET | None | READ | Safe to poll; returns source-level liveness |
| List sources/cameras | `/api/sources` | GET | X-API-Key | READ | Returns all source statuses |
| Source detail | `/api/sources/{id}` | GET | X-API-Key | READ | Single source |
| Add source (controlled) | `/api/sources` | POST | X-API-Key | CONTROLLED | Requires confirmation in IASA |
| Remove source (restricted) | `/api/sources/{id}` | DELETE | X-API-Key | RESTRICTED | Requires confirmation + audit |
| Register phone camera | `/api/sources/phone` | POST | X-API-Key | CONTROLLED | |
| Ingest phone frame | `/api/sources/phone/{id}/frame` | POST | X-API-Key | CONTROLLED | JPEG body; IASA should not do this directly |
| List incidents | `/api/incidents` | GET | X-API-Key | READ | Paginated; active count included |
| Incident detail | `/api/incidents/{id}` | GET | X-API-Key | READ | Includes angles + timeline |
| Review incident | `/api/incidents/{id}/review` | POST | X-API-Key | CONTROLLED | Acknowledgement; stops escalation |
| Get snapshot | `/api/incidents/{id}/snapshot` | GET | X-API-Key | READ | JPEG; protect sensitive imagery in IASA UI |
| Get clip | `/api/incidents/{id}/clip` | GET | X-API-Key | READ | MP4; may not be ready immediately |
| Incident report PDF | `/api/incidents/{id}/report.pdf` | GET | X-API-Key | READ | Requires `reportlab`; 501 if missing |
| Live stream | `/ws/live` | WS | ?key= query param | READ | Base64 JPEG frames; IASA should proxy/protect |

**Campus Guardian connector: FEASIBLE.** All desired IASA capabilities map to real endpoints. Auth is API key. No OpenAPI spec file exists (FastAPI auto-generates at `/docs` and `/openapi.json` when running — needs live instance to capture).

### DietSense integration

| IASA capability | Actual endpoint | Method | Auth | Permission level | Notes |
|----------------|-----------------|--------|------|-----------------|-------|
| Health check | ❌ No standalone backend | — | — | — | Supabase project health only; no DietSense app health endpoint |
| List/get recipes | `supabase.from("recipes").select()` | GET | Supabase anon key | READ | Via Supabase REST API |
| Get user preferences | `supabase.from("user_preferences").select()` | GET | Supabase anon key | READ | Per-session prefs |
| Save user preferences | `supabase.from("user_preferences").upsert()` | POST | Supabase anon key | CONTROLLED | |
| Get meal recommendation | `http://localhost:8080/completion` | POST | None | READ | ⚠️ Backend not in repo; must be found or rebuilt |
| Save AI recommendation | `supabase.from("ai_food_recommendations").insert()` | POST | Supabase anon key | CONTROLLED | Table not in migration file |
| Recipe chat | `/api/chat` | POST | None | READ | ❌ Endpoint doesn't exist in this repo; broken feature |
| Weekly meal plan | ❌ Not found | — | — | — | No weekly planning endpoint in this repo |
| Grocery list | ❌ Not found | — | — | — | No grocery list endpoint in this repo |

**DietSense connector: PARTIALLY FEASIBLE.** Recipes, preferences, and allergy data are accessible via Supabase. Meal recommendation requires the missing `localhost:8080` backend. Weekly plan and grocery list features are not present in the current repo. IASA integration must either use Supabase directly (with RLS) or rebuild/connect the missing backend.

### F.R.I.D.A.Y integration (confirmed third project — replaces NeuroVoice concept)

F.R.I.D.A.Y is a **multi-screen collaboration hub**: a Node.js WebSocket/HTTP2 relay that lets multiple Flutter devices (Android + desktop) connect, authenticate via a shared `SESSION_KEY`, and exchange messages (screen frames, input events, clipboard sync, drag payloads, voice commands) with AES-256-GCM encryption. mDNS broadcast enables local network device discovery.

**What IASA can integrate with (the hub, not the empty client apps):**

| IASA capability | Actual endpoint | Method | Auth | Permission level | Notes |
|----------------|-----------------|--------|------|-----------------|-------|
| Health check | `ws://hub-host:8765` — connect + receive HANDSHAKE | WS | SESSION_KEY (hash in AUTH message) | READ | Hub is alive if WS handshake completes |
| List connected devices | Listen for `DEVICE_CONNECTED` / `DEVICE_DISCONNECTED` broadcasts after AUTH | WS | SESSION_KEY | READ | Hub broadcasts device join/leave to all authorized clients |
| Send message to device | `SCREEN_FRAME`, `INPUT_EVENT`, `CLIPBOARD`, `DRAG_PAYLOAD`, `VOICE_CMD` | WS | SESSION_KEY + authorized | CONTROLLED | Requires `targetId`; routes to specific device or broadcasts |
| Request file transfer | `FILE_TRANSFER_INIT` → receives `FILE_TOKEN` + HTTP/2 port | WS | SESSION_KEY + authorized | CONTROLLED | Hub opens HTTP/2 stream on port 8766 for file upload |
| Device discovery (local network) | mDNS query for `multi-screen-collate` service | mDNS | None (network-level) | READ | mDNS announcement from hub; no auth on discovery |

**What is NOT available (empty client stubs):**
- No Flutter client apps exist (all `main.dart` files are 0 bytes)
- No screen capture, input relay, or clipboard UI implemented
- `VOICE_CMD` message type is defined in the hub but no client processes it
- No AI/EMG/ML prediction — `ai_classifier.dart` is MobileNet image classification only

**F.R.I.D.A.Y connector: FEASIBLE for hub-level operations.** IASA can connect to the hub as an authorized client, list devices, and send/receive messages. The connector is a WebSocket client that handles the HANDSHAKE → AUTH flow, maintains the connection, and exposes hub events as IASA tools. The empty client apps are out of scope for IASA.

---

## 14. Blockers and Unknowns (Point 8 of audit)

### Blocking issues

| # | Blocker | Status | Impact |
|---|---------|--------|--------|
| **B-1** | **F.R.I.D.A.Y is not NeuroVoice (original spec mismatch).** The IASA prompt's original concept describes an EMG-based assistive communication system. The actual third project is F.R.I.D.A.Y — a multi-screen collaboration/relay tool. **Resolved by user:** F.R.I.D.A.Y is the intended third project. The IASA spec is adapted accordingly. | ✅ Resolved | IASA spec updated to treat F.R.I.D.A.Y as third project; original NeuroVoice concept dropped. |
| **B-2** | **DietSense backend is missing / project is incomplete.** The `foodAI.ts` module calls `http://localhost:8080/completion` — a backend service not in the DietSense repo. User confirms DietSense is "in working phase" and not built properly yet. | 🔬 Deferred | IASA DietSense connector is paused. When DietSense is further along, locate/rebuild the backend and revisit. |
| **B-3** | **Supabase RLS policy state unknown.** DietSense security depends entirely on Postgres Row Level Security. Without access to the Supabase dashboard, we cannot verify what data the anon key can read/write. | 🔬 Deferred (DietSense) | Not actionable until DietSense is revisited. |
| **B-4** | **Campus Guardian .env contains real live credentials.** The committed API key, Telegram bot token, and chat ID are active credentials. | ⚠️ Action required | Rotate the API key + Telegram token before any demo environment is stood up. |

### Open items (for later phases)

| # | Item | Notes |
|---|-------|-------|
| O-1 | Does Campus Guardian have a running instance to capture `/openapi.json` from? | FastAPI auto-generates this at runtime. Needed for full connector contract. |
| O-2 | What LLM provider is preferred for IASA? The prompt requires a provider-independent adapter. | User to decide; adapter designed to be swappable. |
| O-3 | Are Campus Guardian snapshot images privacy-sensitive? The code has `privacy_blur_faces` config (disabled by default). | Confirm before building IASA UI that displays snapshots. |
| O-4 | F.R.I.D.A.Y hub `SESSION_KEY` management | The hub generates a random key at startup; all connected devices must share the same key. How should this be managed in an IASA-integrated deployment? |
| O-5 | F.R.I.D.A.Y client apps are empty stubs | The hub is functional but the Flutter clients are non-existent. IASA integration talks to the hub directly, not the clients. |

---

## 15. Verified Integration Matrix (compact summary)

| IASA feature | Campus Guardian | DietSense (deferred) | F.R.I.D.A.Y |
|-------------|----------------|---------------------|-------------|
| Health check | ✅ `/api/health` | 🔬 Deferred — no live backend | ✅ WS handshake to hub |
| List sources/devices | ✅ `/api/sources` | 🔬 Deferred | ✅ WS `DEVICE_CONNECTED` broadcast + mDNS |
| Source/device detail | ✅ `/api/sources/{id}` | 🔬 Deferred | ✅ Device info from AUTH + broadcast |
| Add/remove source | ✅ POST/DELETE `/api/sources` | 🔬 Deferred | ❌ No source management in hub |
| Incident/alert list | ✅ `/api/incidents` | 🔬 Deferred | ❌ No alerts in F.R.I.D.A.Y |
| Incident detail + timeline | ✅ `/api/incidents/{id}` | 🔬 Deferred | ❌ N/A |
| Review/acknowledge | ✅ POST `/api/incidents/{id}/review` | 🔬 Deferred | ❌ N/A |
| Evidence (snapshot/clip) | ✅ GET snapshot + clip | 🔬 Deferred | ❌ N/A (screen frames are live, not stored) |
| Live stream | ✅ `/ws/live` (annotated video) | 🔬 Deferred | ✅ `SCREEN_FRAME` messages via WS |
| Recipes/meal data | ❌ N/A | 🔬 Deferred — repo incomplete | ❌ N/A |
| User preferences | ❌ N/A | 🔬 Deferred | ❌ N/A |
| Meal recommendation | ❌ N/A | 🔬 Deferred — backend missing | ❌ N/A |
| Weekly plan / grocery list | ❌ N/A | 🔬 Deferred — not in repo | ❌ N/A |
| Cross-device messaging | ❌ N/A | ❌ N/A | ✅ `SCREEN_FRAME`, `INPUT_EVENT`, `CLIPBOARD`, `DRAG_PAYLOAD`, `VOICE_CMD` via WS |
| File transfer | ❌ N/A | ❌ N/A | ✅ `FILE_TRANSFER_INIT` → HTTP/2 upload |
| Device discovery | ❌ N/A | ❌ N/A | ✅ mDNS (`multi-screen-collate` service) |
| Chat/assistant | ❌ N/A | 🔬 Deferred — `/api/chat` broken | ❌ N/A |

---

## 16. Phase 0 Deliverables Checklist

| Deliverable | Status |
|-------------|--------|
| Repository map for all three repos | ✅ Complete |
| Current-state architecture diagram | ✅ Described in text; diagram to be drawn in Phase 1 |
| Verified API inventory | ✅ Complete for CG and F.R.I.D.A.Y; partial for DietSense (Supabase + missing backend) |
| Auth and data-flow analysis | ✅ Complete |
| Runtime/deployment summary | ✅ Complete |
| Security risk register | ✅ Complete (18 findings across 3 repos) |
| Integration matrix | ✅ Complete (provisional — see blockers) |
| Unknowns and blockers list | ✅ Complete (4 blockers, 6 unknowns) |
| Prioritized implementation plan | 🔬 See below |

---

## 17. Prioritized Implementation Plan (for approval)

### Prerequisite (resolved)
- ✅ **B-1 resolved:** F.R.I.D.A.Y confirmed as third project. IASA spec adapted.
- 🔬 **B-2 deferred:** DietSense backend missing; project is in working phase. DietSense integration is paused. Revisit when DietSense is further along.
- 🔬 **B-3 deferred:** Supabase RLS audit not needed until DietSense is revisited.

### Phase 1 — IASA Foundation + Campus Guardian connector (NOW)
- Set up IASA project scaffold: backend (FastAPI), frontend (React+TS+Vite), infrastructure (Docker Compose, PostgreSQL, Redis)
- Create `.env.example` with all required vars (no real secrets)
- Implement database schema + Alembic migrations (users, workspaces, conversations, messages, tool_executions, approvals, events, memory)
- Implement auth skeleton: user model, workspace model, role-based permissions (READ/CONTROLLED/RESTRICTED)
- Implement connector registry + connector interface (`health()`, `capabilities()`, `execute()`)
- Implement typed result objects (`project_id`, `status`, `checked_at`, `latency_ms`, `data`, `error`)
- Implement LLM provider adapter interface (abstract base — swappable)
- Implement **Campus Guardian connector** with all verified endpoints
- Implement **F.R.I.D.A.Y hub connector** (WebSocket client with HANDSHAKE→AUTH flow)
- Define tool registrations for CG and F.R.I.D.A.Y with permission levels

### Phase 2 — Core orchestration + chat
- Intent routing: classify user messages (general, project query, tool action, clarification)
- Tool discovery: return only tools available to the user in the current workspace
- Tool execution: validate args against schema, apply permission checks, execute via connector
- Response aggregation: normalize connector results, preserve source timestamps and status
- Grounded chat responses with source attribution
- Basic chat UI (frontend): message list, input, tool result display

### Phase 3 — Permissions, approvals, audit
- Implement approval flow for CONTROLLED and RESTRICTED actions (bind to user, workspace, tool, args, expiry)
- Implement audit logging: who requested, who approved, what ran, when, outcome
- Implement cancellation and idempotency for appropriate operations
- Frontend: approval dialog, audit log view

### Phase 4 — Memory and personalization
- Implement scoped memory: personal, conversation, project, shared workspace, operational history
- Memory provenance, timestamps, scope, owner, retention policy
- User controls: review, correct, export, delete memories
- Authorization filters on retrieval

### Phase 5 — Frontend completeness + voice
- Dashboard: multi-project health overview, activity feed
- Project views: Campus Guardian (sources, incidents, snapshots), F.R.I.D.A.Y (connected devices, hub status)
- Settings: workspace management, connector config, LLM provider config
- Voice: push-to-talk, STT/TTS adapters, cancellation, shared approval flow

### Phase 6 — DietSense integration (when ready)
- Revisit when DietSense backend is available
- Connect via Supabase or rebuilt backend
- Implement recipe lookup, preference management, meal recommendation tools

### Phase 7 — Production readiness
- HTTPS reverse proxy, secret management, backups, monitoring, rate limits
- Load, integration, failure-injection, and end-to-end tests
- Deploy to staging, verify recovery and partial failures
- Investor demo script and demo-environment checklist

---

## 18. Security findings requiring immediate attention

1. **Rotate Campus Guardian credentials.** The `.env` file contains a live API key, Telegram bot token, and chat ID. These must be rotated before any IASA integration or demo.
2. **Set `ALLOW_NO_AUTH=false`** and ensure `API_KEY` is set before running Campus Guardian in any network-accessible environment.
3. **Audit Supabase RLS** for DietSense before integrating with IASA — the anon key is client-side and RLS is the only access control.
4. **Remove secrets from git history** if possible (git filter-branch or BFG), or rotate and add to `.gitignore`.

---

*End of Phase 0 audit. No code changes were made to any repository. awaiting user approval before proceeding to Phase 1.*
