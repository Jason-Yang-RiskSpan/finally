'use client';

import type { ConnectionStatus } from '@/lib/types';
import { fmtCurrency, pnlColor } from '@/lib/format';

interface HeaderProps {
  totalValue: number;
  cashBalance: number;
  unrealizedPnl: number;
  connection: ConnectionStatus;
}

const STATUS_LABEL: Record<ConnectionStatus, string> = {
  connected: 'LIVE',
  connecting: 'RECONNECTING',
  disconnected: 'DISCONNECTED',
};

export function Header({
  totalValue,
  cashBalance,
  unrealizedPnl,
  connection,
}: HeaderProps) {
  return (
    <header
      className="flex items-center justify-between border-b border-bg-border bg-bg-elev px-4 py-3"
      data-testid="header"
    >
      <div className="flex items-center gap-3">
        <span className="text-accent-yellow font-bold text-lg tracking-wider">
          FinAlly
        </span>
        <span className="text-xs text-slate-500 uppercase tracking-widest">
          AI Trading Workstation
        </span>
      </div>

      <div className="flex items-center gap-6">
        <div className="text-right">
          <div className="text-[10px] uppercase text-slate-500 tracking-widest">
            Total Value
          </div>
          <div className="text-lg font-semibold text-accent-blue" data-testid="total-value">
            {fmtCurrency(totalValue)}
          </div>
        </div>
        <div className="text-right">
          <div className="text-[10px] uppercase text-slate-500 tracking-widest">
            Cash
          </div>
          <div className="text-lg font-semibold text-slate-200" data-testid="cash-balance">
            {fmtCurrency(cashBalance)}
          </div>
        </div>
        <div className="text-right">
          <div className="text-[10px] uppercase text-slate-500 tracking-widest">
            Unrealized P&amp;L
          </div>
          <div
            className={`text-lg font-semibold ${pnlColor(unrealizedPnl)}`}
            data-testid="unrealized-pnl"
          >
            {fmtCurrency(unrealizedPnl, { sign: true })}
          </div>
        </div>
        <div
          className="flex items-center gap-2 px-2 py-1 rounded border border-bg-border"
          data-testid="connection-status"
          data-status={connection}
          aria-label={`connection-${connection}`}
        >
          <span className={`status-dot ${connection}`} />
          <span className="text-[10px] uppercase tracking-widest text-slate-400">
            {STATUS_LABEL[connection]}
          </span>
        </div>
      </div>
    </header>
  );
}
