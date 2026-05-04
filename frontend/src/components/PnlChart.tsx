'use client';

// Portfolio total-value over time. Sourced from /api/portfolio/history, with
// the in-memory `liveTotal` appended as a virtual final point so the line
// follows the live total between snapshot writes.

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { PortfolioSnapshot } from '@/lib/types';
import { fmtCurrency } from '@/lib/format';

interface PnlChartProps {
  snapshots: PortfolioSnapshot[];
  liveTotal?: number;
}

export function PnlChart({ snapshots, liveTotal }: PnlChartProps) {
  const data = snapshots.map((s, i) => ({
    i,
    t: s.recorded_at,
    total: s.total_value,
  }));
  if (typeof liveTotal === 'number' && Number.isFinite(liveTotal)) {
    data.push({ i: data.length, t: 'now', total: liveTotal });
  }

  return (
    <section className="panel flex flex-col" data-testid="pnl-chart">
      <div className="panel-header">
        <span>Portfolio Value</span>
        {data.length > 0 && (
          <span className="text-slate-200 normal-case tracking-normal">
            {fmtCurrency(data[data.length - 1].total)}
          </span>
        )}
      </div>
      <div className="p-2 flex-1 min-h-[160px]">
        {data.length < 2 ? (
          <div className="h-full flex items-center justify-center text-slate-500 text-sm">
            Awaiting snapshots…
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 6, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid stroke="#1f242c" strokeDasharray="3 3" />
              <XAxis dataKey="i" hide />
              <YAxis
                domain={['dataMin', 'dataMax']}
                width={64}
                tick={{ fontSize: 10, fill: '#8b95a5' }}
                axisLine={{ stroke: '#2a2f3a' }}
                tickLine={false}
                tickFormatter={(v) => `$${Math.round(v).toLocaleString()}`}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#0d1117',
                  border: '1px solid #2a2f3a',
                  fontSize: 12,
                }}
                formatter={(v: number) => [fmtCurrency(v), 'Total']}
                labelFormatter={(_, payload) => payload?.[0]?.payload?.t ?? ''}
              />
              <Line
                type="monotone"
                dataKey="total"
                stroke="#ecad0a"
                strokeWidth={1.5}
                dot={false}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </section>
  );
}
