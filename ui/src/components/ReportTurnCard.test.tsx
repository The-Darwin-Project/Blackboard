// BlackBoard/ui/src/components/ReportTurnCard.test.tsx
// @ai-rules:
// 1. [Pattern]: Style assertions read inline styles via data-testid hooks (report-turn-card/-header); the markdown body is the [data-color-mode] wrapper (wrapperElement is strictly typed, no data-testid); jsdom serializes colors as rgb().
// 2. [Constraint]: ACTOR_LABELS has no 'developer' entry, so unmapped actors render the raw actor string; tests pin that fallback.
// 3. [Gotcha]: Global RTL cleanup lives in src/testSetup.ts -- do not add per-file afterEach(cleanup).
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import ReportTurnCard from './ReportTurnCard';
import type { ParsedTurn } from '../utils/parseReport';

vi.mock('./MermaidBlock', () => ({
  default: ({ code }: { code: string }) => <div data-testid="mermaid-block">{code}</div>,
}));

function makeParsedTurn(overrides: Partial<ParsedTurn> = {}): ParsedTurn {
  return {
    number: 1,
    actor: 'brain',
    action: 'triage',
    time: '10:00:00',
    delta: '+5s',
    body: 'Report body text',
    ...overrides,
  };
}

// MarkdownPreview applies its `style` prop to the element carrying data-color-mode.
const queryBody = () => document.querySelector<HTMLElement>('[data-color-mode="dark"]');
function getBody(): HTMLElement {
  const el = queryBody();
  if (!el) throw new Error('markdown body wrapper not found');
  return el;
}

function renderCard(overrides: Partial<ParsedTurn> = {}) {
  return render(<ReportTurnCard turn={makeParsedTurn(overrides)} />);
}

describe('ReportTurnCard', () => {
  describe('actor label resolution (ACTOR_LABELS)', () => {
    it('maps actor "user" to "User"', () => {
      renderCard({ actor: 'user' });
      expect(screen.getByText('User')).toBeInTheDocument();
    });

    it('maps actor "brain" to "FRIDAY"', () => {
      renderCard({ actor: 'brain' });
      expect(screen.getByText('FRIDAY')).toBeInTheDocument();
    });

    it('falls back to the raw actor string for unmapped actors (developer, architect)', () => {
      const { unmount } = renderCard({ actor: 'developer' });
      expect(screen.getByText('developer')).toBeInTheDocument();
      expect(screen.queryByText('Developer')).toBeNull();
      unmount();

      renderCard({ actor: 'architect' });
      expect(screen.getByText('architect')).toBeInTheDocument();
    });
  });

  describe('card container styles', () => {
    it('renders a 3px actor-colored left border (user = #ec4899)', () => {
      renderCard({ actor: 'user' });
      const card = screen.getByTestId('report-turn-card');
      expect(card.style.borderLeftWidth).toBe('3px');
      expect(card.style.borderLeftStyle).toBe('solid');
      expect(card.style.borderLeftColor).toBe('rgb(236, 72, 153)');
    });

    it('uses the developer actor color (#10b981) for the left border', () => {
      renderCard({ actor: 'developer' });
      const card = screen.getByTestId('report-turn-card');
      expect(card.style.borderLeftColor).toBe('rgb(16, 185, 129)');
    });

    it('falls back to #6b7280 for an actor with no color mapping', () => {
      renderCard({ actor: 'some_unknown_actor' });
      const card = screen.getByTestId('report-turn-card');
      expect(card.style.borderLeftColor).toBe('rgb(107, 114, 128)');
    });

    it('applies card radius, padding, margin and background', () => {
      renderCard();
      const card = screen.getByTestId('report-turn-card');
      expect(card.style.borderRadius).toBe('8px');
      expect(card.style.padding).toBe('10px 14px');
      expect(card.style.marginBottom).toBe('16px');
      expect(card.style.backgroundColor).toBe('rgba(15, 23, 42, 0.55)');
    });

    it('lets the header row wrap', () => {
      renderCard();
      const header = screen.getByTestId('report-turn-header');
      expect(header.style.display).toBe('flex');
      expect(header.style.flexWrap).toBe('wrap');
    });
  });

  describe('content and header metadata', () => {
    it('renders action, time, delta and markdown body', () => {
      renderCard({ action: 'execute', time: '12:34:56', delta: '+1m', body: 'Hello **report**' });
      const header = screen.getByTestId('report-turn-header');
      expect(header.textContent).toContain('execute');
      expect(header.textContent).toContain('12:34:56');
      expect(header.textContent).toContain('+1m');
      const body = getBody();
      expect(body.textContent).toContain('Hello');
      expect(body.querySelector('strong')?.textContent).toBe('report');
    });

    it('wraps the markdown body with overflowX: auto to prevent horizontal blowout', () => {
      renderCard({ body: '```ts\nconst reallyLongLine = 1;\n```' });
      const body = getBody();
      expect(body.style.overflowX).toBe('auto');
    });

    it('omits the markdown body when the turn body is empty', () => {
      renderCard({ body: '' });
      expect(queryBody()).toBeNull();
    });

    it('shows the AI-generated badge for non-user actors only', () => {
      const { unmount } = renderCard({ actor: 'brain' });
      expect(screen.getByText('AI-generated')).toBeInTheDocument();
      unmount();

      renderCard({ actor: 'user' });
      expect(screen.queryByText('AI-generated')).toBeNull();
    });

    it('renders mermaid fences through MermaidBlock', () => {
      renderCard({ body: '```mermaid\ngraph TD; A-->B;\n```' });
      expect(screen.getByTestId('mermaid-block').textContent).toContain('graph TD');
    });
  });
});
