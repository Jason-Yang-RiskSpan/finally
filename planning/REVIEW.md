# REVIEW.md — PLAN.md Review

## Findings

### High

1. **Conflicting DB initialization contract (`lazy on first request` vs `startup only`)**  
   - `PLAN.md` states lazy initialization in Key Boundaries ([PLAN.md](/Users/jasonyang/Documents/finally/planning/PLAN.md:113)), but later defines startup initialization as the decided behavior ([PLAN.md](/Users/jasonyang/Documents/finally/planning/PLAN.md:218), [PLAN.md](/Users/jasonyang/Documents/finally/planning/PLAN.md:552)).  
   - Risk: backend teams may implement different init paths, creating duplicate seed logic or race conditions.
   - Recommended fix: keep one source of truth (startup init), and remove/update the lazy-init sentence in §4.

2. **SSE resume semantics are underspecified for `Last-Event-ID`**  
   - The plan requires honoring `Last-Event-ID` ([PLAN.md](/Users/jasonyang/Documents/finally/planning/PLAN.md:212), [PLAN.md](/Users/jasonyang/Documents/finally/planning/PLAN.md:549)) but does not define event ID format, retention window, or behavior after process restart where in-memory history is lost.
   - Risk: inconsistent client/server behavior and flaky reconnection tests.
   - Recommended fix: specify exact semantics (e.g., monotonically increasing numeric IDs; if ID is older than buffer or server restarted, send current snapshot + continue).

3. **Trade input validation rules are incomplete for numeric bounds**  
   - API lists `{ticker, quantity, side}` ([PLAN.md](/Users/jasonyang/Documents/finally/planning/PLAN.md:311)) and schema allows fractional `REAL` quantities ([PLAN.md](/Users/jasonyang/Documents/finally/planning/PLAN.md:247), [PLAN.md](/Users/jasonyang/Documents/finally/planning/PLAN.md:257)), but no explicit constraints for `quantity > 0`, finite numbers, max precision, or max order size.
   - Risk: zero/negative/NaN/over-precision edge cases can create undefined portfolio math and DB inconsistencies.
   - Recommended fix: define validation contract (e.g., `0 < quantity <= X`, decimal precision limit, reject non-finite values) and HTTP error codes.

### Medium

4. **Timestamp format is ambiguous (`ISO timestamp`)**  
   - Multiple tables specify “ISO timestamp” ([PLAN.md](/Users/jasonyang/Documents/finally/planning/PLAN.md:234), [PLAN.md](/Users/jasonyang/Documents/finally/planning/PLAN.md:240), [PLAN.md](/Users/jasonyang/Documents/finally/planning/PLAN.md:270), [PLAN.md](/Users/jasonyang/Documents/finally/planning/PLAN.md:278)), and history endpoint uses `?since=<iso8601>` ([PLAN.md](/Users/jasonyang/Documents/finally/planning/PLAN.md:312)) without timezone/precision rules.
   - Risk: parsing drift across frontend/backend/tests.
   - Recommended fix: standardize on UTC RFC3339 (e.g., `2026-05-03T15:04:05.123Z`) and document parse/validation behavior.

5. **Environment requirements are contradictory for local/test modes**  
   - `OPENROUTER_API_KEY` is marked required ([PLAN.md](/Users/jasonyang/Documents/finally/planning/PLAN.md:124)), while `LLM_MOCK=true` explicitly supports development without an API key ([PLAN.md](/Users/jasonyang/Documents/finally/planning/PLAN.md:405-408)).
   - Risk: startup checks may incorrectly hard-fail in mock mode.
   - Recommended fix: clarify conditional requirement: API key required only when `LLM_MOCK=false`.

6. **"Single Docker command opens browser" is not universally true**  
   - First-launch section promises browser auto-open ([PLAN.md](/Users/jasonyang/Documents/finally/planning/PLAN.md:15)), while scripts only say “optionally opens the browser” ([PLAN.md](/Users/jasonyang/Documents/finally/planning/PLAN.md:482)).
   - Risk: acceptance criteria mismatch and failed expectations in CI/headless environments.
   - Recommended fix: reword to “prints URL; scripts may open browser when supported.”

## Open Questions

1. Should `/api/watchlist/{ticker}` be case-insensitive on input but normalized to uppercase at persistence boundary?
2. Should `/api/portfolio/history` return ascending or descending time order, and is there a max row limit/default window?
3. For failed LLM actions in `actions` JSON, should `reason` be from a fixed enum for frontend-safe rendering/tests?

## Summary

The plan is strong and implementation-oriented, but a few contract-level ambiguities (init path, SSE resume, trade validation) are likely to cause divergent behavior across agents unless clarified before coding proceeds.
