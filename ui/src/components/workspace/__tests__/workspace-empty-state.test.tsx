// BlackBoard/ui/src/components/workspace/__tests__/workspace-empty-state.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import WorkspaceEmptyState from '../WorkspaceEmptyState';
import * as client from '../../../api/client';

vi.mock('../../../api/client', () => ({
  createChatEvent: vi.fn(),
}));

describe('WorkspaceEmptyState (T-5)', () => {
  const mockOnSelectEvent = vi.fn();
  let queryClient: QueryClient;

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
  });

  const renderWithProviders = (ui: React.ReactElement) => {
    return render(
      <QueryClientProvider client={queryClient}>
        {ui}
      </QueryClientProvider>
    );
  };

  it('renders greeting title and prompt chips', () => {
    renderWithProviders(<WorkspaceEmptyState onSelectEvent={mockOnSelectEvent} />);

    expect(screen.getByText(/What would you like to build|Ask Darwin|Workspace|How can I help/i)).toBeInTheDocument();
    // Chips
    expect(screen.getByText(/Review PR/i)).toBeInTheDocument();
    expect(screen.getByText(/Debug Pipeline/i)).toBeInTheDocument();
  });

  it('populates prompt or submits when prompt chip is clicked', () => {
    renderWithProviders(<WorkspaceEmptyState onSelectEvent={mockOnSelectEvent} />);

    const chip = screen.getByText(/Review PR/i);
    fireEvent.click(chip);

    const input = screen.getByPlaceholderText(/message|ask|prompt|instruct/i) as HTMLInputElement | HTMLTextAreaElement;
    expect(input.value).toMatch(/Review PR/i);
  });

  it('calls createChatEvent and onSelectEvent on submission', async () => {
    vi.mocked(client.createChatEvent).mockResolvedValueOnce({
      event_id: 'evt-new-123',
      status: 'created',
    } as any);

    renderWithProviders(<WorkspaceEmptyState onSelectEvent={mockOnSelectEvent} />);

    const input = screen.getByPlaceholderText(/message|ask|prompt|instruct/i);
    fireEvent.change(input, { target: { value: 'Diagnose memory leak' } });
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' });

    expect(client.createChatEvent).toHaveBeenCalledWith(
      'Diagnose memory leak',
      'general'
    );
  });
});
