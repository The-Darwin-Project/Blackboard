// BlackBoard/ui/src/components/workspace/CopyButton.tsx
import { useState, useRef, useEffect } from 'react';
import type { MouseEvent, KeyboardEvent } from 'react';
import { Copy, Check } from 'lucide-react';

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

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  const triggerCopySuccess = () => {
    if (!mountedRef.current) return;
    if (timerRef.current) clearTimeout(timerRef.current);
    setCopied(true);
    timerRef.current = setTimeout(() => {
      if (mountedRef.current) setCopied(false);
    }, 2000);
  };

  const handleCopy = async () => {
    if (!text) return;
    // eslint-disable-next-line no-control-regex
    const sanitized = text.replace(/[\r\n\x1b]/g, '');

    if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
      try {
        await navigator.clipboard.writeText(sanitized);
        triggerCopySuccess();
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
      if (success) triggerCopySuccess();
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

  const handleKeyDown = (e: KeyboardEvent<HTMLButtonElement>) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.stopPropagation();
      e.preventDefault();
      if (text) void handleCopy();
    }
  };

  const disabled = !text;
  const currentLabel = copied
    ? (label.startsWith('Copy ') ? `Copied ${label.slice(5)}` : 'Copied!')
    : label;
  const currentTitle = copied ? 'Copied!' : label;

  return (
    <button
      type="button"
      disabled={disabled}
      aria-label={currentLabel}
      title={currentTitle}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
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
