'use client';
import { useEffect, useRef, useState, type ReactNode } from 'react';

/** Sticky Masthead: hides after 64px of scrolling down, returns on scroll up, gains shadow-pop once
 *  scrolled (03-Layouts, "Shell"). Off under prefers-reduced-motion (handled in site.css). */
export function SiteHeader({ children }: { children: ReactNode }) {
  const [state, setState] = useState({ scrolled: false, hidden: false });
  const last = useRef(0);
  useEffect(() => {
    let frame = 0;
    const onScroll = () => {
      if (frame) return;
      frame = requestAnimationFrame(() => {
        frame = 0;
        const y = window.scrollY;
        const down = y > last.current;
        last.current = y;
        setState({ scrolled: y > 0, hidden: down && y > 64 });
      });
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => { window.removeEventListener('scroll', onScroll); if (frame) cancelAnimationFrame(frame); };
  }, []);
  return (
    <div className="site-header" data-scrolled={state.scrolled || undefined} data-hidden={state.hidden || undefined}
      onFocusCapture={() => setState((s) => ({ ...s, hidden: false }))}>
      {children}
    </div>
  );
}
