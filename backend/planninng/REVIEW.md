# REVIEW.md

## Findings

### 1) High — Contradictory DB initialization contract
- `PLAN.md` says backend lazily initializes DB on first request in Key Boundaries (`backend/db/`) ([PLAN.md](/Users/jasonyang/Documents/finally/planning/PLAN.md:113)).
- Later it says DB initialization is startup-only ([PLAN.md](/Users/jasonyang/Documents/finally/planning/PLAN.md:218)) and decision log confirms startup-only ([PLAN.md](/Users/jasonyang/Documents/finally/planning/PLAN.md:552)).
- Risk: backend/frontend engineers may implement different lifecycle behavior, causing race conditions or duplicate init logic.
- Recommendation: keep one source of truth (startup-only), remove/replace the lazy-init sentence in §4.

### 2) High — SSE resume requirement is underspecified/infeasible as written
- Spec requires `Last-Event-ID` resume support ([PLAN.md](/Users/jasonyang/Documents/finally/planning/PLAN.md:212), [PLAN.md](/Users/jasonyang/Documents/finally/planning/PLAN.md:549)).
- No `id:` field format or replay buffer contract is defined in the SSE payload section ([PLAN.md](/Users/jasonyang/Documents/finally/planning/PLAN.md:206)).
- Risk: implementations may claim resume support but cannot replay missed updates correctly.
- Recommendation: define event `id` semantics (for example, cache version) and explicit replay behavior/window.

### 3) Medium — “Required API key” conflicts with mock/degraded mode
- `OPENROUTER_API_KEY` is labeled required ([PLAN.md](/Users/jasonyang/Documents/finally/planning/PLAN.md:124)).
- `LLM_MOCK=true` explicitly supports development without a key ([PLAN.md](/Users/jasonyang/Documents/finally/planning/PLAN.md:405)).
- First-launch UX promises immediate usability ([PLAN.md](/Users/jasonyang/Documents/finally/planning/PLAN.md:15)).
- Risk: ambiguous startup behavior (fail-fast vs run with chat degraded).
- Recommendation: specify exact behavior matrix by env combination, especially when `LLM_MOCK=false` and key missing.

### 4) Medium — Primary key rule conflicts with `users_profile` schema
- Plan says all tables use `INTEGER PRIMARY KEY AUTOINCREMENT` ([PLAN.md](/Users/jasonyang/Documents/finally/planning/PLAN.md:229)).
- `users_profile` instead uses `user_id` as primary key with no `id` ([PLAN.md](/Users/jasonyang/Documents/finally/planning/PLAN.md:231)).
- Risk: inconsistent migrations/tests due to contradictory schema contract.
- Recommendation: restate rule as “all tables except `users_profile`” or add a surrogate `id` there too.

### 5) Low — Startup simplicity vs chat dependency clarity
- Single-command startup and immediate usage are emphasized ([PLAN.md](/Users/jasonyang/Documents/finally/planning/PLAN.md:15)).
- Chat still depends on external API key unless mock mode is enabled ([PLAN.md](/Users/jasonyang/Documents/finally/planning/PLAN.md:140)).
- Risk: unclear user expectation when chat is unavailable on first run.
- Recommendation: document explicit first-run chat UX when key is absent (banner, disabled input, or default mock mode).

## Open Questions
- Should `/api/chat` stay available in degraded mode without `OPENROUTER_API_KEY` when `LLM_MOCK=false`, or should startup fail?
- Is SSE reconnection intended to be lossless replay or best-effort latest-state sync?

## Summary
The plan is solid and implementable, but these contract conflicts (DB init timing, SSE resume semantics, and env/key behavior) should be resolved before parallel implementation to prevent divergence and rework.
