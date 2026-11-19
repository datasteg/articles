'use client';
import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState, type KeyboardEvent, type ReactNode } from 'react';
import { createPortal } from 'react-dom';

/** A link that opens a small non-modal dialog: on hover (pointer), keyboard focus, or tap/click.
 *  Escape or a click outside closes it; under 600px it becomes a bottom sheet (CSS).
 *  Without JavaScript it is a plain link (to the reference or the glossary entry). */
export function Popover(p: {
  href: string; label: string; closeLabel: string; className?: string; popClass?: string;
  trigger: ReactNode; children: ReactNode;
}) {
  const id = useId();
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<{ top: number; left: number; above: boolean } | null>(null);
  const [mounted, setMounted] = useState(false);
  const trig = useRef<HTMLAnchorElement>(null);
  const pop = useRef<HTMLDivElement>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const refocusing = useRef(false); // focus returned by Escape/close must not reopen it
  const hoverBlocked = useRef(false); // after a close, hover reopens only once the pointer has left the link
  useEffect(() => setMounted(true), []);

  const clear = () => { if (timer.current) clearTimeout(timer.current); timer.current = null; };
  const later = (fn: () => void, ms: number) => { clear(); timer.current = setTimeout(fn, ms); };
  const close = useCallback((refocus = false) => {
    clear(); setOpen(false); hoverBlocked.current = true;
    if (refocus) { refocusing.current = true; trig.current?.focus(); refocusing.current = false; }
  }, []);

  const place = useCallback(() => {
    const t = trig.current, el = pop.current;
    if (!t) return;
    const r = t.getBoundingClientRect();
    const vw = window.innerWidth, vh = window.innerHeight;
    const pw = el?.offsetWidth ?? 360, ph = el?.offsetHeight ?? 220;
    const above = r.bottom + 8 + ph > vh - 8 && r.top - 8 - ph > 8;
    const left = Math.max(12, Math.min(r.left - 24, vw - pw - 12));
    setPos({ top: above ? r.top - 8 - ph : r.bottom + 8, left, above });
  }, []);

  useLayoutEffect(() => { if (open) place(); }, [open, place]);
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e: globalThis.KeyboardEvent) => { if (e.key === 'Escape') close(true); };
    const onDown = (e: PointerEvent) => {
      const n = e.target as Node;
      if (!pop.current?.contains(n) && !trig.current?.contains(n)) close();
    };
    const onMove = () => place();
    document.addEventListener('keydown', onKey);
    document.addEventListener('pointerdown', onDown);
    window.addEventListener('scroll', onMove, { passive: true });
    window.addEventListener('resize', onMove);
    return () => {
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('pointerdown', onDown);
      window.removeEventListener('scroll', onMove);
      window.removeEventListener('resize', onMove);
    };
  }, [open, close, place]);
  useEffect(() => () => clear(), []);

  function onKeyDown(e: KeyboardEvent<HTMLAnchorElement>) {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setOpen((o) => !o); }
    if (e.key === 'ArrowDown' && open) { e.preventDefault(); pop.current?.querySelector<HTMLElement>('a, button')?.focus(); }
  }

  return (
    <>
      <a ref={trig} href={p.href} className={p.className} aria-haspopup="dialog" aria-expanded={open} aria-controls={open ? id : undefined}
        onClick={(e) => { e.preventDefault(); clear(); setOpen((o) => !o); }}
        onKeyDown={onKeyDown}
        onPointerEnter={(e) => { if (e.pointerType === 'mouse' && !hoverBlocked.current) later(() => setOpen(true), 140); }}
        onPointerLeave={(e) => { hoverBlocked.current = false; if (e.pointerType === 'mouse' && open) later(() => { setOpen(false); }, 260); }}
        onFocus={(e) => { if (!refocusing.current && e.currentTarget.matches(':focus-visible')) setOpen(true); }}>
        {p.trigger}
      </a>
      {open && mounted ? createPortal(
        <div ref={pop} id={id} role="dialog" aria-label={p.label} className={'ac-pop' + (p.popClass ? ' ' + p.popClass : '')}
          style={pos ? { top: pos.top + 'px', left: pos.left + 'px' } : { visibility: 'hidden', top: 0, left: 0 }}
          onPointerEnter={(e) => { if (e.pointerType === 'mouse') clear(); }}
          onPointerLeave={(e) => { if (e.pointerType === 'mouse') later(() => setOpen(false), 260); }}
          onClick={(e) => { if ((e.target as HTMLElement).closest('a[href^="#"]')) close(); }}>
          <button type="button" className="ac-pop__close" aria-label={p.closeLabel} onClick={() => close(true)}>
            <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round"><path d="M6 6l12 12M18 6 6 18" /></svg>
          </button>
          {p.children}
        </div>,
        document.body,
      ) : null}
    </>
  );
}
