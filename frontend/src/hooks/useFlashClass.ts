'use client';

// Returns a className 'flash-up' | 'flash-down' | '' that auto-clears after
// ~500ms. The hook keys off `flashKey` so consecutive same-direction flashes
// each retrigger the animation.

import { useEffect, useState } from 'react';

export function useFlashClass(
  flash: 'up' | 'down' | null,
  flashKey: number,
  durationMs = 500,
): string {
  const [className, setClassName] = useState('');
  useEffect(() => {
    if (!flash) return;
    setClassName(flash === 'up' ? 'flash-up' : 'flash-down');
    const t = setTimeout(() => setClassName(''), durationMs);
    return () => clearTimeout(t);
  }, [flash, flashKey, durationMs]);
  return className;
}
