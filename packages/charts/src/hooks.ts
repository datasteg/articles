'use client';
import { useEffect, useState, type RefObject } from 'react';

/** The element's width, measured after hydration (server render uses `fallback`).
 *  `ready` turns true once a real measurement has been taken; charts expose it as data-ready
 *  so screenshots can wait for the final layout. */
export function useWidth(ref: RefObject<HTMLElement | null>, fallback: number): { width: number; ready: boolean } {
  const [state, setState] = useState({ width: fallback, ready: false });
  useEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    const measure = () => {
      const w = Math.round(el.getBoundingClientRect().width);
      if (w > 0) setState((s) => (s.width === w && s.ready ? s : { width: w, ready: true }));
    };
    measure();
    if (typeof ResizeObserver === 'undefined') return undefined;
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, [ref]);
  return state;
}
