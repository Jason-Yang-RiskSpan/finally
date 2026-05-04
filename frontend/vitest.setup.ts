import '@testing-library/jest-dom/vitest';

// jsdom: ResizeObserver is missing; Recharts uses it in ResponsiveContainer.
class MockResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}
(globalThis as unknown as { ResizeObserver: typeof MockResizeObserver }).ResizeObserver =
  (globalThis as unknown as { ResizeObserver?: typeof MockResizeObserver }).ResizeObserver ||
  MockResizeObserver;
