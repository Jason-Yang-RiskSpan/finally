'use client';

// Tiny SVG sparkline. Hand-rolled to avoid pulling in a charting lib for a
// 60-point inline visualization. Renders flat line if fewer than 2 points.

import { memo } from 'react';

interface SparklineProps {
  values: number[];
  width?: number;
  height?: number;
  color?: string;
}

function SparklineImpl({
  values,
  width = 80,
  height = 22,
  color = '#209dd7',
}: SparklineProps) {
  if (!values || values.length < 2) {
    return (
      <svg
        width={width}
        height={height}
        role="img"
        aria-label="sparkline"
        data-testid="sparkline"
        data-points={values?.length ?? 0}
      >
        <line
          x1={0}
          y1={height / 2}
          x2={width}
          y2={height / 2}
          stroke="#2a2f3a"
          strokeWidth={1}
        />
      </svg>
    );
  }
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const stepX = width / (values.length - 1);
  const points = values
    .map((v, i) => `${(i * stepX).toFixed(2)},${(height - ((v - min) / range) * height).toFixed(2)}`)
    .join(' ');
  const direction =
    values[values.length - 1] >= values[0] ? '#16a34a' : '#ef4444';
  return (
    <svg
      width={width}
      height={height}
      role="img"
      aria-label="sparkline"
      data-testid="sparkline"
      data-points={values.length}
    >
      <polyline
        points={points}
        fill="none"
        stroke={color === 'auto' ? direction : color}
        strokeWidth={1.25}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}

export const Sparkline = memo(SparklineImpl);
