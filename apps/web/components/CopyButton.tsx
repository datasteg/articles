'use client';
import { useState } from 'react';

/** A small button that copies `text` and says so for a moment. Without JavaScript it does nothing; the text is selectable. */
export function CopyButton({ text, label, done }: { text: string; label: string; done: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch { /* clipboard blocked: the reader can still select the text */ }
  };
  return (
    <button type="button" className="gl-btn gl-btn--secondary gl-btn--sm cite-copy" data-done={copied || undefined} onClick={copy}>
      <span aria-live="polite">{copied ? done : label}</span>
    </button>
  );
}
