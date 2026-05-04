'use client';

// Hand-rolled treemap. We want full control over the cash tile, the color
// scaling, and the zero-position case. The squarified-treemap algorithm is
// overkill here; a simple binary-split (slice-and-dice) packer keeps tiles
// readable for ~10 positions without external deps.

import type { Position } from '@/lib/types';
import { fmtCurrency, fmtPct } from '@/lib/format';

export interface HeatmapTile {
  key: string;
  label: string;
  value: number; // weight (positive)
  pnlPct: number | null; // null for cash
  isCash?: boolean;
  subtitle?: string;
}

interface HeatmapProps {
  positions: Position[];
  cashBalance: number;
  totalValue: number;
  width?: number;
  height?: number;
}

// Color scale: red→neutral→green based on pnl % (clamped to ±5%).
function pnlColor(pnlPct: number | null): string {
  if (pnlPct == null) return '#3b4252'; // cash neutral
  const clamped = Math.max(-5, Math.min(5, pnlPct));
  const t = clamped / 5; // -1..1
  if (t >= 0) {
    // green ramp
    const intensity = 0.25 + 0.55 * t;
    return `rgba(22, 163, 74, ${intensity.toFixed(3)})`;
  }
  const intensity = 0.25 + 0.55 * -t;
  return `rgba(239, 68, 68, ${intensity.toFixed(3)})`;
}

interface PackedRect {
  x: number;
  y: number;
  w: number;
  h: number;
  tile: HeatmapTile;
}

// Slice-and-dice: split along the longer axis, proportional to tile values.
function pack(
  tiles: HeatmapTile[],
  x: number,
  y: number,
  w: number,
  h: number,
): PackedRect[] {
  if (tiles.length === 0) return [];
  if (tiles.length === 1) {
    return [{ x, y, w, h, tile: tiles[0] }];
  }
  const total = tiles.reduce((a, t) => a + t.value, 0) || 1;
  // Greedily split the array roughly in half by value.
  let acc = 0;
  let splitIdx = 1;
  for (let i = 0; i < tiles.length; i++) {
    acc += tiles[i].value;
    if (acc >= total / 2) {
      splitIdx = Math.max(1, i + 1);
      break;
    }
  }
  const left = tiles.slice(0, splitIdx);
  const right = tiles.slice(splitIdx);
  const leftTotal = left.reduce((a, t) => a + t.value, 0);
  const ratio = leftTotal / total;
  if (w >= h) {
    const splitW = w * ratio;
    return [
      ...pack(left, x, y, splitW, h),
      ...pack(right, x + splitW, y, w - splitW, h),
    ];
  } else {
    const splitH = h * ratio;
    return [
      ...pack(left, x, y, w, splitH),
      ...pack(right, x, y + splitH, w, h - splitH),
    ];
  }
}

export function buildTiles(
  positions: Position[],
  cashBalance: number,
  totalValue: number,
): HeatmapTile[] {
  const tiles: HeatmapTile[] = [];
  for (const p of positions) {
    if (!p.market_value || p.market_value <= 0) continue;
    tiles.push({
      key: p.ticker,
      label: p.ticker,
      value: p.market_value,
      pnlPct: p.unrealized_pl_percent,
      subtitle: fmtCurrency(p.market_value),
    });
  }
  const safeTotal = totalValue > 0 ? totalValue : Math.max(cashBalance, 1);
  if (cashBalance > 0) {
    tiles.push({
      key: 'CASH',
      label: 'CASH',
      value: cashBalance,
      pnlPct: null,
      isCash: true,
      subtitle: fmtCurrency(cashBalance),
    });
  }
  // If for some reason no tiles, synthesize a cash tile so the heatmap is never blank.
  if (tiles.length === 0) {
    tiles.push({
      key: 'CASH',
      label: 'CASH',
      value: Math.max(cashBalance, safeTotal),
      pnlPct: null,
      isCash: true,
      subtitle: fmtCurrency(Math.max(cashBalance, safeTotal)),
    });
  }
  // Largest first improves visual ordering.
  tiles.sort((a, b) => b.value - a.value);
  return tiles;
}

export function Heatmap({
  positions,
  cashBalance,
  totalValue,
  width = 360,
  height = 240,
}: HeatmapProps) {
  const tiles = buildTiles(positions, cashBalance, totalValue);
  const rects = pack(tiles, 0, 0, width, height);

  return (
    <section className="panel flex flex-col" data-testid="heatmap">
      <div className="panel-header">
        <span>Portfolio Heatmap</span>
      </div>
      <div className="p-2 flex-1">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          width="100%"
          height="100%"
          preserveAspectRatio="none"
          role="img"
          aria-label="portfolio-heatmap"
        >
          {rects.map((r) => (
            <g key={r.tile.key} data-testid={`heat-tile-${r.tile.key}`}>
              <rect
                x={r.x}
                y={r.y}
                width={r.w}
                height={r.h}
                fill={pnlColor(r.tile.pnlPct)}
                stroke="#0d1117"
                strokeWidth={2}
              />
              {r.w > 40 && r.h > 24 && (
                <>
                  <text
                    x={r.x + 6}
                    y={r.y + 16}
                    fill={r.tile.isCash ? '#cbd5e1' : '#fff'}
                    fontFamily="ui-monospace, monospace"
                    fontWeight={700}
                    fontSize={Math.min(14, Math.max(10, Math.min(r.w, r.h) / 6))}
                  >
                    {r.tile.label}
                  </text>
                  {r.h > 44 && (
                    <text
                      x={r.x + 6}
                      y={r.y + 32}
                      fill="rgba(255,255,255,0.85)"
                      fontFamily="ui-monospace, monospace"
                      fontSize={10}
                    >
                      {r.tile.subtitle}
                    </text>
                  )}
                  {r.h > 60 && r.tile.pnlPct != null && (
                    <text
                      x={r.x + 6}
                      y={r.y + 46}
                      fill="rgba(255,255,255,0.85)"
                      fontFamily="ui-monospace, monospace"
                      fontSize={10}
                    >
                      {fmtPct(r.tile.pnlPct)}
                    </text>
                  )}
                </>
              )}
            </g>
          ))}
        </svg>
      </div>
    </section>
  );
}
