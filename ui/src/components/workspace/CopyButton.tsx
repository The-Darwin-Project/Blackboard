// BlackBoard/ui/src/components/workspace/CopyButton.tsx
// @ai-rules:
// 1. [Constraint]: Native <button type="button"> only; do NOT add a custom onKeyDown. The browser already fires onClick for Enter/Space,
//    and a duplicate key handler double-copies on Firefox. Parent row key handlers are shielded by the row's e.target !== e.currentTarget guard.
// 2. [Constraint]: Text is sanitized before it reaches the clipboard (ANSI sequences, C0/DEL/C1 controls, U+2028/U+2029, bidi controls) via
//    sanitizeClipboardText from utils/clipboard.ts (kept out of this file for react-refresh/only-export-components).
// 3. [Pattern]: Feedback ('copied') is transient (2000ms) and is reset, with its timer, whenever the `text` prop changes or the component unmounts.
//    A copy that resolves after `text` changed must not flag the new value as copied (guarded by textRef).
// 4. [Gotcha]: execCommand('copy') returning false is a failure (no 'copied' state); the temporary textarea is always removed in finally.
import { useState, useRef, useEffect } from 'react';
import type { MouseEvent } from 'react';
import { Copy, Check } from 'lucide-react';
import { sanitizeClipboardText } from '../../utils/clipboard';

export interface CopyButtonProps {
  text: string | null | undefined;
  label?: string;
  className?: string;
  iconSize?: number;
}

export function CopyButton({ text, label = 'Copy Event ID', className = '', iconSize = 12 }: CopyButtonProps) {
  const [copied, setCopied] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);
  const textRef = useRef(text);
  textRef.current = text;

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = null;
    };
  }, []);

  // A different value must never inherit the previous value's "Copied" feedback.
  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = null;
    setCopied(false);
  }, [text]);

  const triggerCopySuccess = (copiedText: string) => {
    if (!mountedRef.current || textRef.current !== copiedText) return;
    if (timerRef.current) clearTimeout(timerRef.current);
    setCopied(true);
    timerRef.current = setTimeout(() => {
      timerRef.current = null;
      if (mountedRef.current) setCopied(false);
    }, 2000);
  };

  const handleCopy = async () => {
    if (!text) return;
    const requested = text;
    const sanitized = sanitizeClipboardText(requested);

    if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
      try {
        await navigator.clipboard.writeText(sanitized);
        triggerCopySuccess(requested);
        return;
      } catch {
        // Fall back to execCommand
      }
    }

    let textarea: HTMLTextAreaElement | null = null;
    try {
      textarea = document.createElement('textarea');
      textarea.value = sanitized;
      textarea.readOnly = true;
      textarea.tabIndex = -1;
      textarea.setAttribute('aria-hidden', 'true');
      textarea.style.position = 'fixed';
      textarea.style.opacity = '0';
      textarea.style.pointerEvents = 'none';
      document.body.appendChild(textarea);
      textarea.select();
      const success = document.execCommand('copy');
      if (success) triggerCopySuccess(requested);
    } catch {
      // Both failed; safely suppress without toggling copied feedback
    } finally {
      if (textarea && textarea.parentNode) {
        textarea.parentNode.removeChild(textarea);
      }
    }
  };

  const handleClick = (e: MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation();
    if (text) void handleCopy();
  };

  const disabled = !text;
  const currentLabel = copied
    ? (label.startsWith('Copy ') ? `Copied ${label.slice(5)}` : 'Copied!')
    : label;

  return (
    <button
      type="button"
      disabled={disabled}
      aria-label={currentLabel}
      title={currentLabel}
      onClick={handleClick}
      className={`inline-flex items-center justify-center p-1 rounded transition-colors ${
        disabled
          ? 'opacity-40 cursor-not-allowed'
          : 'hover:bg-bg-tertiary text-text-muted hover:text-text-primary'
      } ${className}`}
    >
      {copied ? (
        <Check size={iconSize} className="text-emerald-400 animate-in fade-in duration-150" />
      ) : (
        <Copy size={iconSize} className="transition-colors" />
      )}
      <span className="sr-only" aria-live="polite">
        {copied ? currentLabel : ''}
      </span>
    </button>
  );
}

export default CopyButton;
