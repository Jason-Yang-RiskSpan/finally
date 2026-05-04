'use client';

// Collapsible AI chat panel. Renders the assistant `actions` JSON inline so
// the user sees executed/rejected trades and watchlist changes per PLAN §9.

import { useEffect, useRef, useState } from 'react';
import type { ChatActions, ChatMessage } from '@/lib/types';
import { fmtPrice, fmtQty } from '@/lib/format';

interface ChatPanelProps {
  messages: ChatMessage[];
  onSend: (text: string) => Promise<void>;
  busy: boolean;
}

function ActionsBlock({ actions }: { actions: ChatActions }) {
  const trades = actions.trades ?? [];
  const watchlist = actions.watchlist_changes ?? [];
  if (trades.length === 0 && watchlist.length === 0) return null;
  return (
    <ul
      className="mt-2 space-y-1 border-l-2 border-bg-border pl-2 text-xs"
      data-testid="chat-actions"
    >
      {trades.map((t, i) => {
        const ok = t.status === 'executed';
        return (
          <li
            key={`tr-${i}`}
            className={ok ? 'text-up' : 'text-down'}
            data-testid={`action-trade-${i}`}
            data-status={t.status}
          >
            <span className="font-bold uppercase">
              {ok ? 'Executed' : 'Rejected'}:
            </span>{' '}
            {t.side.toUpperCase()} {fmtQty(t.quantity)} {t.ticker}
            {ok && t.price != null ? ` @ ${fmtPrice(t.price)}` : ''}
            {!ok && t.reason ? ` — ${t.reason}` : ''}
          </li>
        );
      })}
      {watchlist.map((w, i) => {
        const ok = w.status === 'executed';
        return (
          <li
            key={`wl-${i}`}
            className={ok ? 'text-accent-blue' : 'text-down'}
            data-testid={`action-watchlist-${i}`}
            data-status={w.status}
          >
            <span className="font-bold uppercase">
              {ok ? 'Watchlist' : 'Rejected'}:
            </span>{' '}
            {w.action} {w.ticker}
            {!ok && w.reason ? ` — ${w.reason}` : ''}
          </li>
        );
      })}
    </ul>
  );
}

function MessageBubble({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === 'user';
  return (
    <div
      className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}
      data-testid={`chat-msg-${msg.role}`}
    >
      <div
        className={`max-w-[85%] rounded px-3 py-2 text-sm ${
          isUser
            ? 'bg-accent-purple/30 border border-accent-purple/60'
            : 'bg-bg-elev border border-bg-border'
        }`}
      >
        <div className="whitespace-pre-wrap">{msg.content}</div>
        {msg.actions && <ActionsBlock actions={msg.actions} />}
      </div>
    </div>
  );
}

export function ChatPanel({ messages, onSend, busy }: ChatPanelProps) {
  const [text, setText] = useState('');
  const [collapsed, setCollapsed] = useState(false);
  const scrollerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const el = scrollerRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages.length, busy]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const t = text.trim();
    if (!t || busy) return;
    setText('');
    await onSend(t);
  }

  if (collapsed) {
    return (
      <aside
        className="panel w-10 flex flex-col items-center justify-center cursor-pointer"
        onClick={() => setCollapsed(false)}
        data-testid="chat-panel-collapsed"
        aria-label="expand-chat"
      >
        <span className="rotate-90 text-xs uppercase tracking-widest text-slate-400">
          AI Chat
        </span>
      </aside>
    );
  }

  return (
    <aside className="panel flex flex-col w-full" data-testid="chat-panel">
      <div className="panel-header">
        <span>AI Assistant</span>
        <button
          type="button"
          className="text-slate-500 hover:text-slate-200 normal-case tracking-normal text-xs"
          onClick={() => setCollapsed(true)}
          aria-label="collapse-chat"
        >
          ▶ Collapse
        </button>
      </div>
      <div
        ref={scrollerRef}
        className="flex-1 overflow-auto p-3 space-y-3 min-h-[200px]"
      >
        {messages.length === 0 && (
          <div className="text-slate-500 text-sm">
            Ask me about your portfolio, request analysis, or tell me to make a
            trade.
          </div>
        )}
        {messages.map((m, i) => (
          <MessageBubble key={m.id ?? i} msg={m} />
        ))}
        {busy && (
          <div className="text-xs text-slate-500" data-testid="chat-loading">
            Thinking…
          </div>
        )}
      </div>
      <form
        onSubmit={submit}
        className="flex gap-2 p-2 border-t border-bg-border"
      >
        <input
          aria-label="chat-input"
          className="input flex-1"
          placeholder="Ask FinAlly…"
          value={text}
          onChange={(e) => setText(e.target.value)}
          disabled={busy}
        />
        <button type="submit" className="btn btn-submit" disabled={busy}>
          Send
        </button>
      </form>
    </aside>
  );
}
