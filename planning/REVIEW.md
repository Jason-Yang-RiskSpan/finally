# Review of PLAN.md

Date: 2026-04-30  
Scope: implementation risk, behavioral ambiguity, and test-coverage gaps

## Findings (ordered by severity)

### 1) High — Monetary math uses floating-point `REAL` for cash, prices, and quantities
- References: PLAN.md lines 233, 247-248, 257-258, 269, 294, 296
- Risk: Floating-point arithmetic will accumulate rounding drift for repeated buys/sells and fractional quantities. That can create false rejects/accepts on cash checks and inconsistent portfolio totals.
- Recommendation: Use fixed-precision storage (integer cents + fixed share scale) or enforce `Decimal` end-to-end with strict quantization rules at API boundaries.
- Test gap: No precision/rounding matrix is specified (e.g., repeated micro-trades, boundary-cost checks).

### 2) High — SSE resume behavior is claimed but not specified enough to implement consistently
- References: PLAN.md lines 181, 208-212, 549
- Risk: The plan says `Last-Event-ID` is honored, but does not define event ID format, replay window, stale-ID behavior, or recovery mode when events are no longer available.
- Recommendation: Define event `id` contract explicitly (e.g., cache version), replay semantics (delta vs full snapshot), and stale/invalid ID fallback behavior.
- Test gap: E2E covers reconnect (line 528) but not deterministic resume correctness with explicit event IDs and missed-update windows.

### 3) High — Trade input validation is incomplete for malformed numeric payloads
- References: PLAN.md lines 311, 381, 504
- Risk: Missing explicit rules for `quantity <= 0`, non-finite numbers, precision limits, and max order size can produce undefined behavior or inconsistent DB state.
- Recommendation: Specify strict trade validation: positive finite quantity, max decimal places, optional notional caps, normalized ticker casing, and exact error responses.
- Test gap: Current edge cases are business-level; sanitization and numeric-boundary tests are not enumerated.

### 4) Medium — Symbol regex is too narrow for many valid real-market tickers
- References: PLAN.md lines 198, 541
- Risk: `^[A-Z]{1,5}$` blocks valid symbols with punctuation (for example class-share formats), creating avoidable watchlist failures in real-data mode.
- Recommendation: Expand syntax to match intended venues, then rely on data-source probe as authoritative validation.
- Test gap: No tests for dotted/hyphenated/venue-specific symbols.

### 5) Medium — `OPENROUTER_API_KEY` requirement conflicts with documented mock-mode behavior
- References: PLAN.md lines 124-125, 405-408
- Risk: Section 5 says key is required, while section 9 says development/testing can run without it (`LLM_MOCK=true`). This creates startup-policy ambiguity.
- Recommendation: Make requirement conditional: key required only when `LLM_MOCK=false` and chat endpoint is enabled.
- Test gap: No explicit startup tests for missing key in both mock and non-mock modes.

### 6) Medium — Massive-provider failure policy is undefined
- References: PLAN.md lines 137-138, 171-175
- Risk: If `MASSIVE_API_KEY` is present but provider calls fail (rate limit/outage/network), behavior is unclear: fail-fast, retry-only, or fallback to simulator.
- Recommendation: Define explicit degraded-mode policy and health-status semantics (`/api/health` should report provider state).
- Test gap: No provider-failure scenarios in unit/E2E plan.

### 7) Medium — `chat_messages` retention is unbounded
- References: PLAN.md lines 272-279, 344
- Risk: Read path limits to last 20 messages, but storage has no cap/pruning, so long-running environments will grow DB indefinitely.
- Recommendation: Add retention policy (max rows per user or age-based prune) and optional background cleanup.
- Test gap: No long-run data growth tests.

### 8) Low — Decision log numbering has unexplained gaps
- References: PLAN.md lines 553-556
- Risk: Jumping from item 15 to 20/22/23/24 hurts traceability for reviewers.
- Recommendation: Renumber sequentially or add note that omitted IDs map to archived decisions.

## Open Questions
1. Is the product scope strictly U.S. equities, or should symbol formats include ETFs/class-share punctuation from day one?
2. What exact fractional-share precision should be supported (for example, 1e-3 vs 1e-6)?
3. Should chat/trade endpoints have rate limits even in single-user mode to prevent accidental execution loops?

## Summary
The architecture and product flow are coherent, but the most likely implementation divergence is in precision-safe trade math and SSE resume semantics. Clarifying those contracts before implementation will reduce high-impact bugs and cross-agent inconsistency.
