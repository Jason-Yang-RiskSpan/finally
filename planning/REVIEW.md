# REVIEW.md

## Findings

### 1) High — Contradictory DB initialization contract
- `PLAN.md` says backend lazily initializes DB on first request in Key Boundaries (`backend/db/`) ([PLAN.md](/Users/jasonyang/Documents/finally/planning/PLAN.md:113)).
- Later it says DB initialization is at startup only ([PLAN.md](/Users/jasonyang/Documents/finally/planning/PLAN.md:218)) and decision log confirms startup-only ([PLAN.md](/Users/jasonyang/Documents/finally/planning/PLAN.md:552)).
- Risk: backend/frontend engineers may implement different lifecycle behavior, causing race conditions or duplicate init logic.
- Recommendation: keep one source of truth (startup-only), remove/replace the lazy-init sentence in §4.

### 2) High — SSE resume requirement is underspecified/infeasible as written
- Spec requires `Last-Event-ID` resume support ([PLAN.md](/Users/jasonyang/Documents/finally/planning/PLAN.md:212), [PLAN.md](/Users/jasonyang/Documents/finally/planning/PLAN.md:549)).
- But no `id:` field format or replay buffer contract is defined in SSE payload requirements ([PLAN.md](/Users/jasonyang/Documents/finally/planning/PLAN.md:206)).
- Risk: implementations may claim resume support but cannot actually replay missed updates safely.
- Recommendation: define SSE event `id` semantics (e.g., cache version) plus explicit replay window behavior.

### 3) Medium — “Required API key” conflicts with mock/testing mode and first-run UX
- `OPENROUTER_API_KEY` is labeled required ([PLAN.md](/Users/jasonyang/Documents/finally/planning/PLAN.md:124)).
- But `LLM_MOCK=true` is documented to avoid real API calls ([PLAN.md](/Users/jasonyang/Documents/finally/planning/PLAN.md:405)) and first launch promises immediate usability ([PLAN.md](/Users/jasonyang/Documents/finally/planning/PLAN.md:15)).
- Risk: ambiguous startup validation logic (hard-fail without key vs allow app with degraded chat).
- Recommendation: specify exact behavior: key required only when `LLM_MOCK=false` and chat endpoint returns clear degraded-mode error when missing.

### 4) Medium — Schema rule conflicts with `users_profile` definition
- Plan states “All tables use `INTEGER PRIMARY KEY AUTOINCREMENT` for their `id` column” ([PLAN.md](/Users/jasonyang/Documents/finally/planning/PLAN.md:229)).
- `users_profile` is defined with `user_id` as the primary key and no `id` column ([PLAN.md](/Users/jasonyang/Documents/finally/planning/PLAN.md:231)).
- Risk: migration/schema drift and test failures caused by contradictory DDL assumptions.
- Recommendation: revise the rule to “all tables except `users_profile`” or add a surrogate `id` consistently.

### 5) Low — Single-command startup claim vs env dependency clarity
- UX says user runs one Docker command and immediately uses app ([PLAN.md](/Users/jasonyang/Documents/finally/planning/PLAN.md:15)).
- Plan also implies LLM feature depends on `.env` key configuration ([PLAN.md](/Users/jasonyang/Documents/finally/planning/PLAN.md:140)).
- Risk: unclear onboarding expectations if chat is broken on first launch without key.
- Recommendation: explicitly state expected first-run behavior without API key (chat disabled with banner, or default `LLM_MOCK=true` for local demo).

## Open Questions
- Should chat endpoint be available in degraded mode when `OPENROUTER_API_KEY` is absent and `LLM_MOCK=false`, or should startup fail fast?
- For SSE resume, is lossless replay required, or is best-effort latest-state sync acceptable?

## Summary
The plan is strong and implementation-oriented, but a few conflicting contracts (DB init timing, SSE resume semantics, and env/key requirements) should be resolved before parallel agent implementation to avoid divergence and rework.
