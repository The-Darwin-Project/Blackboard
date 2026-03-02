// BlackBoard/ui/src/components/SourceIcon.tsx
// @ai-rules:
// 1. [Constraint]: Pure presentational -- no external icon libs, inline SVG only.
// 2. [Pattern]: Unknown sources get a generic circle-dot fallback.
// 3. [Gotcha]: Each SVG must include aria-hidden + wrapper title for tooltip a11y.

interface SourceIconProps {
  source: string;
  size?: number;
}

const ICON_COLOR = '#94a3b8';

function SlackIcon({ size }: { size: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <rect x="1" y="6" width="3" height="6" rx="1" fill="#E01E5A" />
      <rect x="6" y="1" width="3" height="6" rx="1" fill="#36C5F0" />
      <rect x="6" y="9" width="3" height="6" rx="1" fill="#2EB67D" />
      <rect x="11" y="4" width="3" height="6" rx="1" fill="#ECB22E" />
    </svg>
  );
}

function GitLabIcon({ size }: { size: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="M8 14.5L1.5 9.5L3 2L5 7.5H11L13 2L14.5 9.5L8 14.5Z" fill="#E24329" />
      <path d="M8 14.5L5 7.5H11L8 14.5Z" fill="#FC6D26" />
    </svg>
  );
}

function HeadhunterIcon({ size }: { size: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="M8 13L2.5 9L3.8 3L5.5 7.5H10.5L12.2 3L13.5 9L8 13Z" fill="#E24329" opacity="0.85" />
      <path d="M8 13L5.5 7.5H10.5L8 13Z" fill="#FC6D26" opacity="0.85" />
      <circle cx="12" cy="4" r="3.5" stroke="#38bdf8" strokeWidth="1.2" fill="none" />
      <line x1="14.5" y1="6.5" x2="15.5" y2="7.5" stroke="#38bdf8" strokeWidth="1.2" strokeLinecap="round" />
    </svg>
  );
}

function GitHubIcon({ size }: { size: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill={ICON_COLOR} aria-hidden="true">
      <path d="M8 1C4.13 1 1 4.13 1 8c0 3.09 2 5.71 4.78 6.64.35.06.48-.15.48-.34 0-.17-.01-.61-.01-.99-1.94.42-2.35-.94-2.35-.94-.32-.81-.78-1.02-.78-1.02-.63-.43.05-.42.05-.42.7.05 1.07.72 1.07.72.62 1.07 1.63.76 2.03.58.06-.45.24-.76.44-.94-1.55-.18-3.18-.78-3.18-3.46 0-.76.27-1.39.72-1.88-.07-.18-.31-.89.07-1.85 0 0 .59-.19 1.93.72a6.7 6.7 0 013.5 0c1.34-.91 1.93-.72 1.93-.72.38.96.14 1.67.07 1.85.45.49.72 1.12.72 1.88 0 2.69-1.63 3.28-3.19 3.45.25.22.48.65.48 1.3 0 .94-.01 1.7-.01 1.93 0 .19.13.41.48.34C13 13.71 15 11.09 15 8c0-3.87-3.13-7-7-7z" />
    </svg>
  );
}

function ChatIcon({ size }: { size: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="M2 3a1 1 0 011-1h10a1 1 0 011 1v7a1 1 0 01-1 1H5l-3 3V3z" stroke={ICON_COLOR} strokeWidth="1.5" strokeLinejoin="round" />
    </svg>
  );
}

function AlignerIcon({ size }: { size: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="M9.5 1L6 7h4l-3.5 8L13 6.5H8.5L11.5 1H9.5z" fill="#f59e0b" />
    </svg>
  );
}

function FallbackIcon({ size }: { size: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <circle cx="8" cy="8" r="6" stroke={ICON_COLOR} strokeWidth="1.5" />
      <circle cx="8" cy="8" r="2" fill={ICON_COLOR} />
    </svg>
  );
}

const ICON_MAP: Record<string, React.FC<{ size: number }>> = {
  slack: SlackIcon,
  gitlab: GitLabIcon,
  headhunter: HeadhunterIcon,
  github: GitHubIcon,
  chat: ChatIcon,
  aligner: AlignerIcon,
};

export default function SourceIcon({ source, size = 16 }: SourceIconProps) {
  const Icon = ICON_MAP[source.toLowerCase()] || FallbackIcon;

  return (
    <span title={source} style={{ display: 'inline-flex', alignItems: 'center', verticalAlign: 'middle' }}>
      <Icon size={size} />
      <span style={{ position: 'absolute', width: 1, height: 1, margin: -1, padding: 0, overflow: 'hidden', clipPath: 'inset(50%)', borderWidth: 0, whiteSpace: 'nowrap' }}>
        {source}
      </span>
    </span>
  );
}
