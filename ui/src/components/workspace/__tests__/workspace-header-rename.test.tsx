// BlackBoard/ui/src/components/workspace/__tests__/workspace-header-rename.test.tsx
// @ai-rules:
// 1. [Constraint]: Component unit tests for WorkspaceHeader inline title editing.
// 2. [Pattern]: RTL render with MemoryRouter, mock useOpsControl and updateEventTitle API.
// 3. [Security]: Verifies Enter commit, Esc cancel, whitespace no-op, and API error alert display.
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import WorkspaceHeader from '../WorkspaceHeader';
import * as api from '../../../api/client';

const opsState = {
  registeredAgents: [{ role: 'developer', status: 'idle', bound_event_id: 'evt-100' }],
  ephemeralAgents: [],
  selectedEventId: 'evt-100',
};

vi.mock('../../../contexts/OpsStateContext', () => ({
  useOpsControl: () => opsState,
}));

let mockEventDoc: { id: string; service: string; status: string; title?: string | null; title_source?: string | null } = {
  id: 'evt-100',
  service: 'payment-service',
  status: 'active',
  title: 'Fix Payment Webhook Timeout',
  title_source: 'llm',
};

vi.mock('../../../hooks/useQueue', () => ({
  useEventDocument: (id: string) => ({
    data: id === 'evt-100' ? mockEventDoc : null,
  }),
}));

describe('WorkspaceHeader Inline Rename (T-6)', () => {
  beforeEach(() => {
    mockEventDoc = {
      id: 'evt-100',
      service: 'payment-service',
      status: 'active',
      title: 'Fix Payment Webhook Timeout',
      title_source: 'llm',
    };
    vi.restoreAllMocks();
  });

  const renderHeader = () =>
    render(
      <MemoryRouter>
        <WorkspaceHeader
          selectedEventId="evt-100"
          isSessionsOpen={true}
          isInspectorOpen={true}
          onToggleSessions={vi.fn()}
          onToggleInspector={vi.fn()}
        />
      </MemoryRouter>
    );

  it('renders the existing event title when present', () => {
    renderHeader();
    expect(screen.getByText('Fix Payment Webhook Timeout')).toBeInTheDocument();
  });

  it('enters editing mode when clicking the rename button or title', () => {
    renderHeader();
    const editBtn = screen.getByRole('button', { name: /rename event|edit title/i });
    fireEvent.click(editBtn);

    const input = screen.getByRole('textbox', { name: /event title/i });
    expect(input).toBeInTheDocument();
    expect(input).toHaveValue('Fix Payment Webhook Timeout');
  });

  it('commits title update on Enter and calls updateEventTitle API', async () => {
    const updateTitleSpy = vi.spyOn(api, 'updateEventTitle').mockResolvedValue({
      id: 'evt-100',
      title: 'Investigate DB Connection Leak',
      title_source: 'user',
    });

    renderHeader();
    const editBtn = screen.getByRole('button', { name: /rename event|edit title/i });
    fireEvent.click(editBtn);

    const input = screen.getByRole('textbox', { name: /event title/i });
    fireEvent.change(input, { target: { value: 'Investigate DB Connection Leak' } });
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' });

    await waitFor(() => {
      expect(updateTitleSpy).toHaveBeenCalledWith('evt-100', 'Investigate DB Connection Leak');
    });
  });

  it('cancels editing without API call when pressing Escape', () => {
    const updateTitleSpy = vi.spyOn(api, 'updateEventTitle').mockResolvedValue({
      id: 'evt-100',
      title: '',
      title_source: 'user',
    });

    renderHeader();
    const editBtn = screen.getByRole('button', { name: /rename event|edit title/i });
    fireEvent.click(editBtn);

    const input = screen.getByRole('textbox', { name: /event title/i });
    fireEvent.change(input, { target: { value: 'Abandoned Title' } });
    fireEvent.keyDown(input, { key: 'Escape', code: 'Escape' });

    expect(updateTitleSpy).not.toHaveBeenCalled();
    expect(screen.queryByRole('textbox', { name: /event title/i })).not.toBeInTheDocument();
    expect(screen.getByText('Fix Payment Webhook Timeout')).toBeInTheDocument();
  });

  it('reverts without API call when submitted title is whitespace only', () => {
    const updateTitleSpy = vi.spyOn(api, 'updateEventTitle');

    renderHeader();
    const editBtn = screen.getByRole('button', { name: /rename event|edit title/i });
    fireEvent.click(editBtn);

    const input = screen.getByRole('textbox', { name: /event title/i });
    fireEvent.change(input, { target: { value: '    ' } });
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' });

    expect(updateTitleSpy).not.toHaveBeenCalled();
    expect(screen.queryByRole('textbox', { name: /event title/i })).not.toBeInTheDocument();
  });

  it('displays error alert banner when updateEventTitle API call fails (T-UI-4)', async () => {
    vi.spyOn(api, 'updateEventTitle').mockRejectedValue(new Error('Network error'));

    renderHeader();
    const editBtn = screen.getByRole('button', { name: /rename event|edit title/i });
    fireEvent.click(editBtn);

    const input = screen.getByRole('textbox', { name: /event title/i });
    fireEvent.change(input, { target: { value: 'Faulty Title' } });
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' });

    await waitFor(() => {
      expect(screen.getByRole('alert').textContent).toContain('Failed to rename event');
    });
  });
});
