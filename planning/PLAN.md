# FinAlly — AI Trading Workstation

## Project Specification

## 1. Vision

FinAlly (Finance Ally) is a visually stunning AI-powered trading workstation that streams live market data, lets users trade a simulated portfolio, and integrates an LLM chat assistant that can analyze positions and execute trades on the user's behalf. It looks and feels like a modern Bloomberg terminal with an AI copilot.

This is the capstone project for an agentic AI coding course. It is built entirely by Coding Agents demonstrating how orchestrated AI agents can produce a production-quality full-stack application. Agents interact through files in `planning/`.

## 2. User Experience

### First Launch

The user runs a single Docker command (or a provided start script). A browser opens to `http://localhost:8000`. No login, no signup. They immediately see:

- A watchlist of 10 default tickers with live-updating prices in a grid
- $10,000 in virtual cash
- A dark, data-rich trading terminal aesthetic
- An AI chat panel ready to assist

### What the User Can Do

- **Watch prices stream** — prices flash green (uptick) or red (downtick) with subtle CSS animations that fade
- **View sparkline mini-charts** — price action beside each ticker in the watchlist, accumulated on the frontend from the SSE stream since page load (sparklines fill in progressively)
- **Click a ticker** to see a larger detailed chart in the main chart area
- **Buy and sell shares** — market orders only, instant fill at current price, no fees, no confirmation dialog
- **Monitor their portfolio** — a heatmap (treemap) showing positions sized by weight and colored by P&L, plus a P&L chart tracking total portfolio value over time
- **View a positions table** — ticker, quantity, average cost, current price, unrealized P&L, % change
- **Chat with the AI assistant** — ask about their portfolio, get analysis, and have the AI execute trades and manage the watchlist through natural language
- **Manage the watchlist** — add/remove tickers manually or via the AI chat

### Visual Design

- **Dark theme**: backgrounds around `#0d1117` or `#1a1a2e`, muted gray borders, no pure black
- **Price flash animations**: brief green/red background highlight on price change, fading over ~500ms via CSS transitions
- **Connection status indicator**: a small colored dot (green = connected, yellow = reconnecting, red = disconnected) visible in the header
- **Professional, data-dense layout**: inspired by Bloomberg/trading terminals — every pixel earns its place
- **Responsive but desktop-first**: optimized for wide screens, functional on tablet

### Color Scheme
- Accent Yellow: `#ecad0a`
- Blue Primary: `#209dd7`
- Purple Secondary: `#753991` (submit buttons)

## 3. Architecture Overview

### Single Container, Single Port

```
┌─────────────────────────────────────────────────┐
│  Docker Container (port 8000)                   │
│                                                 │
│  FastAPI (Python/uv)                            │
│  ├── /api/*          REST endpoints             │
│  ├── /api/stream/*   SSE streaming              │
│  └── /*              Static file serving         │
│                      (Next.js export)            │
│                                                 │
│  SQLite database (volume-mounted)               │
│  Background task: market data polling/sim        │
└─────────────────────────────────────────────────┘
```

- **Frontend**: Next.js with TypeScript, built as a static export (`output: 'export'`), served by FastAPI as static files
- **Backend**: FastAPI (Python), managed as a `uv` project
- **Database**: SQLite, single file at `db/finally.db`, volume-mounted for persistence
- **Real-time data**: Server-Sent Events (SSE) — simpler than WebSockets, one-way server→client push, works everywhere
- **AI integration**: LiteLLM → OpenRouter (Cerebras for fast inference), with structured outputs for trade execution
- **Market data**: Environment-variable driven — simulator by default, real data via Massive API if key provided

### Why These Choices

| Decision | Rationale |
|---|---|
| SSE over WebSockets | One-way push is all we need; simpler, no bidirectional complexity, universal browser support |
| Static Next.js export | Single origin, no CORS issues, one port, one container, simple deployment |
| SQLite over Postgres | No auth = no multi-user = no need for a database server; self-contained, zero config |
| Single Docker container | Students run one command; no docker-compose for production, no service orchestration |
| uv for Python | Fast, modern Python project management; reproducible lockfile; what students should learn |
| Market orders only | Eliminates order book, limit order logic, partial fills — dramatically simpler portfolio math |

---

## 4. Directory Structure

```
finally/
├── frontend/                 # Next.js TypeScript project (static export)
├── backend/                  # FastAPI uv project (Python)
│   └── db/                   # Schema definitions, seed data, migration logic
├── planning/                 # Project-wide documentation for agents
│   ├── PLAN.md               # This document
│   └── ...                   # Additional agent reference docs
├── scripts/
│   ├── start_mac.sh          # Launch Docker container (macOS/Linux)
│   ├── stop_mac.sh           # Stop Docker container (macOS/Linux)
│   ├── start_windows.ps1     # Launch Docker container (Windows PowerShell)
│   └── stop_windows.ps1      # Stop Docker container (Windows PowerShell)
├── test/                     # Playwright E2E tests + docker-compose.test.yml
├── db/                       # Volume mount target (SQLite file lives here at runtime)
│   └── .gitkeep              # Directory exists in repo; finally.db is gitignored
├── Dockerfile                # Multi-stage build (Node → Python)
├── docker-compose.yml        # Optional convenience wrapper
├── .env                      # Environment variables (gitignored, .env.example committed)
└── .gitignore
```

### Key Boundaries

- **`frontend/`** is a self-contained Next.js project. It knows nothing about Python. It talks to the backend via `/api/*` endpoints and `/api/stream/*` SSE endpoints. Internal structure is up to the Frontend Engineer agent.
- **`backend/`** is a self-contained uv project with its own `pyproject.toml`. It owns all server logic including database initialization, schema, seed data, API routes, SSE streaming, market data, and LLM integration. Internal structure is up to the Backend/Market Data agents.
- **`backend/db/`** contains schema SQL definitions and seed logic. The backend lazily initializes the database on first request — creating tables and seeding default data if the SQLite file doesn't exist or is empty.
- **`db/`** at the top level is the runtime volume mount point. The SQLite file (`db/finally.db`) is created here by the backend and persists across container restarts via Docker volume.
- **`planning/`** contains project-wide documentation, including this plan. All agents reference files here as the shared contract.
- **`test/`** contains Playwright E2E tests and supporting infrastructure (e.g., `docker-compose.test.yml`). Unit tests live within `frontend/` and `backend/` respectively, following each framework's conventions.
- **`scripts/`** contains start/stop scripts that wrap Docker commands.

---

## 5. Environment Variables

```bash
# Required: OpenRouter API key for LLM chat functionality
OPENROUTER_API_KEY=your-openrouter-api-key-here

# Optional: Massive (Polygon.io) API key for real market data
# If not set, the built-in market simulator is used (recommended for most users)
MASSIVE_API_KEY=

# Optional: Set to "true" for deterministic mock LLM responses (testing)
LLM_MOCK=false
```

### Behavior

- If `MASSIVE_API_KEY` is set and non-empty → backend uses Massive REST API for market data
- If `MASSIVE_API_KEY` is absent or empty → backend uses the built-in market simulator
- If `LLM_MOCK=true` → backend returns deterministic mock LLM responses (for E2E tests)
- The backend reads `.env` from the project root (mounted into the container or read via docker `--env-file`)

### `.env.example`

A committed `.env.example` lists exactly these three keys (with empty/default values) so the first-run experience is self-explanatory:

```bash
OPENROUTER_API_KEY=
MASSIVE_API_KEY=
LLM_MOCK=false
```

---

## 6. Market Data

### Two Implementations, One Interface

Both the simulator and the Massive client implement the same abstract interface. The backend selects which to use based on the environment variable. All downstream code (SSE streaming, price cache, frontend) is agnostic to the source.

### Simulator (Default)

- Generates prices using geometric Brownian motion (GBM) with configurable drift and volatility per ticker
- Updates at ~500ms intervals
- Correlated moves across tickers (e.g., tech stocks move together)
- Occasional random "events" — sudden 2-5% moves on a ticker for drama
- Starts from realistic seed prices (e.g., AAPL ~$190, GOOGL ~$175, etc.)
- Runs as an in-process background task — no external dependencies

### Massive API (Optional)

- REST API polling (not WebSocket) — simpler, works on all tiers
- Polls for the union of all watched tickers on a configurable interval
- Free tier (5 calls/min): poll every 15 seconds
- Paid tiers: poll every 2-15 seconds depending on tier
- Parses REST response into the same format as the simulator

### Shared Price Cache

- A single background task (simulator or Massive poller) writes to an in-memory price cache
- The cache holds the latest price, previous price, timestamp, and a per-ticker **session-open price** (captured the first time the cache sees a ticker after backend startup) for daily-change-% display
- The cache also holds a monotonic **version counter** that increments on every change
- SSE streams read from this cache and push updates to connected clients
- This architecture supports future multi-user scenarios without changes to the data layer

### Tracked Tickers

The set of tickers the backend keeps live is the union of:

1. The current watchlist
2. Any ticker for which the user holds a position (so portfolio valuation is always live, even after a ticker is removed from the watchlist)

The watchlist API and trade execution path each ensure the corresponding ticker is registered with the data source.

### Ticker Validation

When a ticker is added to the watchlist (manually or via LLM), the backend:

1. Applies a syntactic check (`^[A-Z]{1,5}$`); reject obvious garbage with HTTP 400
2. Asks the data source to register the ticker. The simulator seeds it from a default-price table (or a sensible fallback) and starts producing prices; Massive issues a quote — a 404/empty response causes the add to be rejected with a clear error
3. On rejection, no DB write occurs and the user (or LLM) sees the error

This is the same validation path for manual UI adds and LLM-issued `watchlist_changes`.

### SSE Streaming

- Endpoint: `GET /api/stream/prices`
- Long-lived SSE connection; client uses native `EventSource` API
- The server emits an event whenever the cache **version advances** — cadence is therefore set by the data source (≈500ms simulator, ≈15s Massive free tier). No duplicate events; no fixed-rate polling on the wire
- Each event covers all tickers that changed since the previous event
- Each price record contains: ticker, price, previous price, timestamp, change direction, and **session-open** price (so the client can compute daily change % without a separate fetch)
- The server emits a `retry: 3000` field at connection start so reconnects use a sane backoff if the network drops
- Client reconnection: native `EventSource` retry, plus `Last-Event-ID` honored on resume to avoid replaying long histories

---

## 7. Database

### SQLite, initialized at startup

On startup, the backend checks for the SQLite database. If the file doesn't exist or required tables are missing, it creates the schema and seeds default data — including an initial `portfolio_snapshots` row so the P&L chart has a t=0 datapoint of $10,000. This means:

- No separate migration step
- No manual database setup
- Fresh Docker volumes start with a clean, seeded database automatically
- Background tasks can rely on schema being present (no first-request setup race)

### Schema

All tables use `INTEGER PRIMARY KEY AUTOINCREMENT` for their `id` column. All tables include a `user_id` TEXT column defaulting to `"default"`. This is hardcoded for now (single-user) but enables future multi-user support without schema migration.

**users_profile** — User state (cash balance). Single row keyed by `user_id`.
- `user_id` TEXT PRIMARY KEY (default: `"default"`)
- `cash_balance` REAL (default: `10000.0`)
- `created_at` TEXT (ISO timestamp)

**watchlist** — Tickers the user is watching
- `id` INTEGER PRIMARY KEY AUTOINCREMENT
- `user_id` TEXT (default: `"default"`)
- `ticker` TEXT
- `added_at` TEXT (ISO timestamp)
- UNIQUE constraint on `(user_id, ticker)`

**positions** — Current holdings (one row per ticker per user). When a sell zeroes a position, the row is **deleted** (trade history in `trades` is the audit log).
- `id` INTEGER PRIMARY KEY AUTOINCREMENT
- `user_id` TEXT (default: `"default"`)
- `ticker` TEXT
- `quantity` REAL (fractional shares supported)
- `avg_cost` REAL
- `updated_at` TEXT (ISO timestamp)
- UNIQUE constraint on `(user_id, ticker)`

**trades** — Trade history (append-only log)
- `id` INTEGER PRIMARY KEY AUTOINCREMENT
- `user_id` TEXT (default: `"default"`)
- `ticker` TEXT
- `side` TEXT (`"buy"` or `"sell"`)
- `quantity` REAL (fractional shares supported)
- `price` REAL
- `executed_at` TEXT (ISO timestamp)

**portfolio_snapshots** — Portfolio value over time (for P&L chart). Recorded:
- Once at startup/seed (so the chart has a t=0 datapoint)
- Immediately after each trade execution
- On a 30-second heartbeat **only if** `total_value` has changed by more than $0.01 since the last snapshot (idle-tab anti-bloat)

Schema:
- `id` INTEGER PRIMARY KEY AUTOINCREMENT
- `user_id` TEXT (default: `"default"`)
- `total_value` REAL
- `recorded_at` TEXT (ISO timestamp)

**chat_messages** — Conversation history with LLM
- `id` INTEGER PRIMARY KEY AUTOINCREMENT
- `user_id` TEXT (default: `"default"`)
- `role` TEXT (`"user"` or `"assistant"`)
- `content` TEXT
- `actions` TEXT (JSON; null for user messages — see §9 for shape)
- `created_at` TEXT (ISO timestamp)

### Trade Execution Atomicity

Every trade — manual or LLM-issued — runs inside a single SQLite transaction. The cash check uses a conditional UPDATE to avoid the SELECT-then-UPDATE race:

```sql
UPDATE users_profile
   SET cash_balance = cash_balance - :cost
 WHERE user_id = :user_id AND cash_balance >= :cost;
```

If `rowcount == 0`, the trade is rejected as insufficient funds. The position upsert and the `trades` insert occur in the same transaction. This makes double-clicks and concurrent LLM trades safe.

### Default Seed Data

- One user profile: `user_id="default"`, `cash_balance=10000.0`
- Ten watchlist entries: AAPL, GOOGL, MSFT, AMZN, TSLA, NVDA, META, JPM, V, NFLX
- One initial `portfolio_snapshots` row at `total_value=10000.0`

---

## 8. API Endpoints

### Market Data
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/stream/prices` | SSE stream of live price updates |

### Portfolio
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/portfolio` | Current positions, cash balance, total value, unrealized P&L |
| POST | `/api/portfolio/trade` | Execute a trade: `{ticker, quantity, side}`. Atomic transaction with conditional cash UPDATE (see §7). |
| GET | `/api/portfolio/history` | Portfolio snapshots. Accepts `?since=<iso8601>` to bound the response. |

### Watchlist
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/watchlist` | Current watchlist tickers with latest prices |
| POST | `/api/watchlist` | Add a ticker: `{ticker}`. Validated per §6 (syntactic + data-source probe). 400 on invalid syntax, 404 if data source rejects. |
| DELETE | `/api/watchlist/{ticker}` | Remove a ticker. The ticker remains live in the cache if a position is still held (see §6 Tracked Tickers). |

### Chat
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/chat` | Send a message, receive complete JSON response (message + executed actions) |

### System
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check (for Docker/deployment) |

---

## 9. LLM Integration

When writing code to make calls to LLMs, use cerebras-inference skill to use LiteLLM via OpenRouter to the `openrouter/openai/gpt-oss-120b` model with Cerebras as the inference provider. Structured Outputs should be used to interpret the results.

There is an OPENROUTER_API_KEY in the .env file in the project root.

### How It Works

When the user sends a chat message, the backend:

1. Loads the user's current portfolio context (cash, positions with P&L, watchlist with live prices, total portfolio value)
2. Loads the **last 20 messages** from the `chat_messages` table (≈10 turns) for context
3. Constructs a prompt with a system message, portfolio context, conversation history, and the user's new message
4. Calls the LLM via LiteLLM → OpenRouter, requesting structured output, using the cerebras-inference skill
5. Parses the complete structured JSON response
6. Auto-executes any trades or watchlist changes specified in the response. Watchlist additions go through the same validation as manual additions (see §6 — the LLM cannot bypass it). Trades go through the same atomic execution as manual trades (see §7)
7. Stores the message and executed actions in `chat_messages`. The `actions` column holds JSON of this shape:
   ```json
   {
     "trades": [
       {"ticker": "AAPL", "side": "buy", "quantity": 10, "price": 191.42, "status": "executed"},
       {"ticker": "TSLA", "side": "buy", "quantity": 5, "status": "rejected", "reason": "insufficient_cash"}
     ],
     "watchlist_changes": [
       {"ticker": "PYPL", "action": "add", "status": "executed"},
       {"ticker": "ZZZZZ", "action": "add", "status": "rejected", "reason": "unknown_ticker"}
     ]
   }
   ```
8. Returns the complete JSON response to the frontend (no token-by-token streaming — Cerebras inference is fast enough that a loading indicator is sufficient)

### Structured Output Schema

The LLM is instructed to respond with JSON matching this schema:

```json
{
  "message": "Your conversational response to the user",
  "trades": [
    {"ticker": "AAPL", "side": "buy", "quantity": 10}
  ],
  "watchlist_changes": [
    {"ticker": "PYPL", "action": "add"}
  ]
}
```

- `message` (required): The conversational text shown to the user
- `trades` (optional): Array of trades to auto-execute. Each trade goes through the same validation as manual trades (sufficient cash for buys, sufficient shares for sells)
- `watchlist_changes` (optional): Array of watchlist modifications

### Auto-Execution

Trades specified by the LLM execute automatically — no confirmation dialog. This is a deliberate design choice:
- It's a simulated environment with fake money, so the stakes are zero
- It creates an impressive, fluid demo experience
- It demonstrates agentic AI capabilities — the core theme of the course

If a trade fails validation (e.g., insufficient cash), the error is included in the chat response so the LLM can inform the user.

### System Prompt Guidance

The LLM should be prompted as "FinAlly, an AI trading assistant" with instructions to:
- Analyze portfolio composition, risk concentration, and P&L
- Suggest trades with reasoning
- Execute trades when the user asks or agrees
- Manage the watchlist proactively
- Be concise and data-driven in responses
- Always respond with valid structured JSON

### LLM Mock Mode

When `LLM_MOCK=true`, the backend returns deterministic mock responses instead of calling OpenRouter. This enables:
- Fast, free, reproducible E2E tests
- Development without an API key
- CI/CD pipelines

---

## 10. Frontend Design

### Layout

The frontend is a single-page application with a dense, terminal-inspired layout. The specific component architecture and layout system is up to the Frontend Engineer, but the UI should include these elements:

- **Watchlist panel** — grid/table of watched tickers with: ticker symbol, current price (flashing green/red on change), daily change % (computed against the **session-open** price provided by the SSE payload), and a sparkline mini-chart (accumulated from SSE since page load)
- **Main chart area** — larger chart for the currently selected ticker, with at minimum price over time. Clicking a ticker in the watchlist selects it here.
- **Portfolio heatmap** — treemap visualization where each rectangle is a position, sized by portfolio weight, colored by P&L (green = profit, red = loss). **Cash is rendered as its own neutral-colored tile** sized by its share of total portfolio value, so a fresh user (100% cash) sees a full heatmap.
- **P&L chart** — line chart showing total portfolio value over time, using data from `portfolio_snapshots` (seeded with a t=0 datapoint at startup, so the chart is never empty)
- **Positions table** — tabular view of all positions: ticker, quantity, avg cost, current price, unrealized P&L, % change. Zero-quantity positions do not appear (rows are deleted on full sell, see §7).
- **Trade bar** — simple input area: ticker field, quantity field, buy button, sell button. Market orders, instant fill.
- **AI chat panel** — docked/collapsible sidebar. Message input, scrolling conversation history, loading indicator while waiting for LLM response. Trade executions and watchlist changes shown inline as confirmations, rendered from `actions` JSON (§9 schema).
- **Header** — portfolio total value (updating live), connection status indicator, cash balance

### Technical Notes

- Use `EventSource` for SSE connection to `/api/stream/prices`
- Canvas-based charting library preferred (Lightweight Charts or Recharts) for performance
- Price flash effect: on receiving a new price, briefly apply a CSS class with background color transition, then remove it
- In production (single container), all API calls go to the same origin (`/api/*`) — no CORS configuration needed
- Tailwind CSS for styling with a custom dark theme

### Local Development Mode

When iterating outside Docker, agents run two processes:

- **Backend**: `cd backend && uv run uvicorn app.main:app --reload --port 8000`
- **Frontend**: `cd frontend && npm run dev` on port 3000

`frontend/next.config.js` declares a `rewrites()` entry mapping `/api/:path*` and `/api/stream/:path*` to `http://localhost:8000/api/:path*`. This keeps `/api/*` calls origin-relative in code (no env-var-driven base URL) and avoids CORS in dev. The static export used in production has no rewrites because everything is same-origin already.

---

## 11. Docker & Deployment

### Multi-Stage Dockerfile

```
Stage 1: Node 20 slim
  - Copy frontend/
  - npm install && npm run build (produces static export)

Stage 2: Python 3.12 slim
  - Install uv
  - Copy backend/
  - uv sync (install Python dependencies from lockfile)
  - Copy frontend build output into a static/ directory
  - Expose port 8000
  - CMD: uvicorn serving FastAPI app
```

FastAPI serves the static frontend files and all API routes on port 8000.

### Docker Volume

The SQLite database persists via a named Docker volume:

```bash
docker run -v finally-data:/app/db -p 8000:8000 --env-file .env finally
```

The `db/` directory in the project root maps to `/app/db` in the container. The backend writes `finally.db` to this path.

### Start/Stop Scripts

**`scripts/start_mac.sh`** (macOS/Linux):
- Builds the Docker image if not already built (or if `--build` flag passed)
- Runs the container with the volume mount, port mapping, and `.env` file
- Prints the URL to access the app
- Optionally opens the browser

**`scripts/stop_mac.sh`** (macOS/Linux):
- Stops and removes the running container
- Does NOT remove the volume (data persists)

**`scripts/start_windows.ps1`** / **`scripts/stop_windows.ps1`**: PowerShell equivalents for Windows.

All scripts should be idempotent — safe to run multiple times.

### Optional Cloud Deployment

The container is designed to deploy to AWS App Runner, Render, or any container platform. A Terraform configuration for App Runner may be provided in a `deploy/` directory as a stretch goal, but is not part of the core build.

---

## 12. Testing Strategy

### Unit Tests (within `frontend/` and `backend/`)

**Backend (pytest)**:
- Market data: simulator generates valid prices, GBM math is correct, Massive API response parsing works, both implementations conform to the abstract interface
- Portfolio: trade execution logic, P&L calculations, edge cases (selling more than owned, buying with insufficient cash, selling at a loss)
- LLM: structured output parsing handles all valid schemas, graceful handling of malformed responses, trade validation within chat flow
- API routes: correct status codes, response shapes, error handling

**Frontend (React Testing Library or similar)**:
- Component rendering with mock data
- Price flash animation triggers correctly on price changes
- Watchlist CRUD operations
- Portfolio display calculations
- Chat message rendering and loading state

### E2E Tests (in `test/`)

**Infrastructure**: A separate `docker-compose.test.yml` in `test/` that spins up the app container plus a Playwright container. This keeps browser dependencies out of the production image.

**Environment**: Tests run with `LLM_MOCK=true` by default for speed and determinism.

**Key Scenarios**:
- Fresh start: default watchlist appears, $10k balance shown, prices are streaming
- Add and remove a ticker from the watchlist
- Buy shares: cash decreases, position appears, portfolio updates
- Sell shares: cash increases, position updates or disappears
- Portfolio visualization: heatmap renders with correct colors, P&L chart has data points
- AI chat (mocked): send a message, receive a response, trade execution appears inline
- SSE resilience: disconnect and verify reconnection

---

## 13. Decision Log (2026-04-30)

Resolved follow-up decisions, folded into the relevant sections above. Listed here so future readers can see what was explicitly chosen versus left for the implementing agent.

| # | Topic | Decision | Folded into |
|---|---|---|---|
| 1 | SSE cadence | Emit on cache-version advance; cadence tied to data source (≈500ms simulator / ≈15s Massive free tier) | §6 SSE Streaming |
| 2 | Tracked tickers | Watchlist ∪ held positions | §6 Tracked Tickers |
| 3 | Watchlist mutation ↔ data source | Single path validates syntax then probes the source; same path for manual + LLM | §6 Ticker Validation |
| 4 | Ticker validation | Best-effort: `^[A-Z]{1,5}$` + data-source probe; surface errors | §6 Ticker Validation, §8 |
| 5 | Daily change % baseline | Session-open price (captured first time the cache sees the ticker after backend startup); included in SSE payload | §6 Shared Price Cache, §6 SSE, §10 |
| 6 | Position at qty=0 | Delete the row; `trades` table preserves history | §7 positions, §10 Positions table |
| 7 | Heatmap cash | Render cash as its own neutral tile, sized by % of portfolio | §10 Portfolio heatmap |
| 8 | P&L cold start | Seed an initial snapshot at $10,000 on startup so the chart has a t=0 datapoint | §7 portfolio_snapshots, §7 Default Seed Data |
| 9 | `actions` JSON shape | Explicit `{trades:[...], watchlist_changes:[...]}` with `status` and optional `reason` per item | §9 step 7 |
| 10 | Chat history depth | Last 20 messages | §9 step 2 |
| 11 | Snapshot retention | Snapshot only on change >$0.01 + on every trade; `/api/portfolio/history` accepts `?since=` | §7 portfolio_snapshots, §8 |
| 12 | EventSource retry | Server emits `retry: 3000`; honors `Last-Event-ID` on resume | §6 SSE Streaming |
| 13 | Trade-execution race | Single transaction; conditional `UPDATE ... WHERE cash_balance >= cost`; `rowcount==0` ⇒ rejected | §7 Trade Execution Atomicity, §8 |
| 14 | LLM watchlist abuse | LLM `watchlist_changes` go through the same validation as manual adds; cannot bypass | §6 Ticker Validation, §9 step 6 |
| 15 | DB init timing | Startup only (not lazy on first request) | §7 SQLite, initialized at startup |
| 20 | Primary keys | `INTEGER PRIMARY KEY AUTOINCREMENT` for all tables; `users_profile` keyed on `user_id` | §7 Schema |
| 22 | Local dev mode | `next dev` on :3000 with `rewrites()` proxy to uvicorn :8000; same-origin in prod | §10 Local Development Mode |
| 23 | `.env.example` | Three keys: `OPENROUTER_API_KEY`, `MASSIVE_API_KEY`, `LLM_MOCK=false` | §5 `.env.example` |
| 24 | CORS | Same-origin in prod (static export); rewrites avoid CORS in dev | §10 Technical Notes, §10 Local Development Mode |

### Deferred (not addressed)

- **§13/21 — `users_profile` single-row collapse.** Kept as a normal table for clarity; revisit only if no second user-scoped scalar appears.
- **Long-term snapshot downsampling.** With the change-only policy in #11, growth is bounded by user activity rather than wall-clock time. No retention cap shipped; revisit if a long-running install actually accumulates a problem.

