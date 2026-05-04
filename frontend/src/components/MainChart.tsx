'use client';

// Larger chart for the currently selected ticker. Uses Recharts (canvas-like
// SVG; renders fine in jsdom). The series is the in-session sparkline
// accumulated from the SSE stream — the backend doesn't expose intraday OHLC.

import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { LivePrice } from '@/lib/types';
import { fmtPct, fmtPrice, pnlColor } from '@/lib/format';

interface MainChartProps {
  ticker: string | null;
  live: LivePrice | undefined;
}

export function MainChart({ ticker, live }: MainChartProps) {
  const data =
    live?.history?.map((v, i) => ({
      i,
      price: v,
    })) ?? [];

  const dailyPct =
    live && live.session_open
      ? ((live.price - live.session_open) / live.session_open) * 100
      : 0;

  return (
    <section className="panel flex flex-col" data-testid="main-chart">
      <div className="panel-header">
        <span>{ticker ? `Chart · ${ticker}` : 'Chart'}</span>
        {live && (
          <span className="flex items-center gap-3 normal-case tracking-normal">
            <span className="text-slate-200">{fmtPrice(live.price)}</span>
            <span className={pnlColor(dailyPct)}>{fmtPct(dailyPct)}</span>
          </span>
        )}
      </div>
      <div className="flex-1 min-h-[180px] p-2">
        {ticker == null && (
          <div className="h-full flex items-center justify-center text-slate-500 text-sm">
            Select a ticker from the watchlist.
          </div>
        )}
        {ticker != null && data.length < 2 && (
          <div className="h-full flex items-center justify-center text-slate-500 text-sm">
            Collecting price data…
          </div>
        )}
        {ticker != null && data.length >= 2 && (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 6, right: 12, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="mc-fill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#209dd7" stopOpacity={0.5} />
                  <stop offset="100%" stopColor="#209dd7" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="i" hide />
              <YAxis
                domain={['dataMin', 'dataMax']}
                width={56}
                tick={{ fontSize: 10, fill: '#8b95a5' }}
                axisLine={{ stroke: '#2a2f3a' }}
                tickLine={false}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#0d1117',
                  border: '1px solid #2a2f3a',
                  fontSize: 12,
                }}
                labelFormatter={() => ticker ?? ''}
                formatter={(v: number) => [fmtPrice(v), 'Price']}
              />
              <Area
                type="monotone"
                dataKey="price"
                stroke="#209dd7"
                strokeWidth={1.5}
                fill="url(#mc-fill)"
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </section>
  );
}
