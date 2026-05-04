"""System prompt + portfolio-context formatting for the chat handler."""

from __future__ import annotations

from typing import Any

SYSTEM_PROMPT = """\
You are FinAlly, an AI trading assistant inside a simulated trading workstation.

Your job:
- Analyze the user's portfolio composition, concentration risk, and unrealized P&L.
- Suggest trades with brief, data-driven reasoning.
- When the user asks you to trade or agrees to a suggestion, include the trade in
  the structured ``trades`` array so it executes automatically.
- Manage the watchlist proactively. To add or remove tickers, populate
  ``watchlist_changes``.
- Be concise. Lead with numbers. No fluff, no disclaimers about being an AI, no
  warnings about real-money trading — this is a simulated environment with fake
  cash.

Hard rules:
- ALWAYS respond with a single JSON object matching the required schema.
- The ``message`` field is the conversational text the user sees. Keep it short
  and useful.
- Trades may be rejected by the system (insufficient cash, unknown ticker). If a
  prior turn shows a rejected action, acknowledge it briefly and adjust.
- Quantities are share counts (fractional allowed). Sides are exactly "buy" or
  "sell". Watchlist actions are exactly "add" or "remove".
"""


def format_portfolio_context(context: dict[str, Any]) -> str:
    """Render the portfolio snapshot as a compact text block for the prompt.

    ``context`` is whatever the backend's portfolio service returns. We render
    it defensively so partially-populated contexts still work (e.g. fresh user
    with zero positions).
    """
    cash = context.get("cash_balance", 0.0)
    total_value = context.get("total_value", cash)
    positions = context.get("positions") or []
    watchlist = context.get("watchlist") or []

    lines: list[str] = []
    lines.append("=== Portfolio Snapshot ===")
    lines.append(f"Cash: ${cash:,.2f}")
    lines.append(f"Total Value: ${total_value:,.2f}")

    if positions:
        lines.append("Positions:")
        for p in positions:
            ticker = p.get("ticker", "?")
            qty = p.get("quantity", 0)
            avg = p.get("avg_cost", 0.0)
            price = p.get("current_price")
            pnl = p.get("unrealized_pnl")
            pnl_pct = p.get("unrealized_pnl_percent")
            price_s = f"${price:,.2f}" if price is not None else "n/a"
            pnl_s = (
                f"P&L ${pnl:+,.2f} ({pnl_pct:+.2f}%)"
                if pnl is not None and pnl_pct is not None
                else "P&L n/a"
            )
            lines.append(
                f"  - {ticker}: {qty} @ avg ${avg:,.2f} | last {price_s} | {pnl_s}"
            )
    else:
        lines.append("Positions: (none — 100% cash)")

    if watchlist:
        lines.append("Watchlist:")
        for w in watchlist:
            ticker = w.get("ticker", "?")
            price = w.get("price")
            chg_pct = w.get("change_percent")
            price_s = f"${price:,.2f}" if price is not None else "n/a"
            chg_s = f"{chg_pct:+.2f}%" if chg_pct is not None else "n/a"
            lines.append(f"  - {ticker}: {price_s} ({chg_s})")
    else:
        lines.append("Watchlist: (empty)")

    return "\n".join(lines)


def build_messages(
    portfolio_context: dict[str, Any],
    history: list[dict[str, str]],
    user_message: str,
) -> list[dict[str, str]]:
    """Construct the OpenAI-style messages list for the LLM call.

    ``history`` is a list of ``{"role": "user"|"assistant", "content": "..."}``
    in chronological order, already capped to the last 20 entries by the
    handler.
    """
    context_block = format_portfolio_context(portfolio_context)
    system = f"{SYSTEM_PROMPT}\n\n{context_block}"

    messages: list[dict[str, str]] = [{"role": "system", "content": system}]
    for msg in history:
        role = msg.get("role")
        content = msg.get("content", "")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_message})
    return messages
