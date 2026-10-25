// BlackBoard/ui/src/__tests__/HeadhunterQueuePanel.test.tsx
// @ai-rules:
// 1. [Constraint]: getHeadhunterPending and safeOpen are mocked; never hit the network or window.open.
// 2. [Pattern]: No vitest globals -- call RTL cleanup() explicitly in afterEach.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, fireEvent, cleanup } from '@testing-library/react';
import type { HeadhunterTodo } from '../api/client';

const { getHeadhunterPending, safeOpen } = vi.hoisted(() => ({
  getHeadhunterPending: vi.fn(),
  safeOpen: vi.fn(),
}));

vi.mock('../api/client', () => ({ getHeadhunterPending }));
vi.mock('../utils/safeOpen', () => ({ safeOpen }));

import HeadhunterQueuePanel from '../components/HeadhunterQueuePanel';

const base = { priority: 0, author: 'bot', created_at: new Date().toISOString() };
const todo = (o: Partial<HeadhunterTodo>): HeadhunterTodo =>
  ({ ...base, action: 'queued', project_path: 'o/r', target_url: 'https://github.com/o/r/pull/1', ...o }) as HeadhunterTodo;

async function renderPanel(items: HeadhunterTodo[]) {
  getHeadhunterPending.mockResolvedValue(items);
  const view = render(<HeadhunterQueuePanel />);
  await waitFor(() => expect(screen.queryByText('No pending items')).toBeNull());
  return view;
}

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  cleanup();
});

describe('HeadhunterQueuePanel', () => {
  it('shows exactly one NEXT badge, skipping active rows to land on the first queued row', async () => {
    await renderPanel([
      todo({ platform: 'github', pr_number: 1, pr_title: 'active one', action: 'active', queue_position: undefined }),
      todo({ platform: 'github', pr_number: 2, pr_title: 'active two', action: 'active', queue_position: null as unknown as undefined }),
      todo({ platform: 'github', pr_number: 3, pr_title: 'first queued', action: 'queued', queue_position: 1 }),
      todo({ platform: 'github', pr_number: 4, pr_title: 'second queued', action: 'queued', queue_position: 2 }),
    ]);
    const badges = screen.getAllByText('next');
    expect(badges).toHaveLength(1);
    const card = badges[0].closest('a') as HTMLElement;
    expect(card.textContent).toContain('#3 first queued');
  });

  it('does not badge any row when every item is already in progress', async () => {
    await renderPanel([
      todo({ platform: 'github', pr_number: 1, action: 'active' }),
      todo({ platform: 'github', pr_number: 2, action: 'deferred' }),
    ]);
    expect(screen.queryByText('next')).toBeNull();
  });

  it('badges the first GitLab todo when there is no queue state', async () => {
    await renderPanel([
      todo({ mr_iid: 7, mr_title: 'gl mr', action: 'build_failed', project_path: 'g/p', target_url: 'https://gitlab.com/g/p/-/merge_requests/7' }),
      todo({ mr_iid: 8, mr_title: 'gl mr 2', action: 'assigned', project_path: 'g/p', target_url: 'https://gitlab.com/g/p/-/merge_requests/8' }),
    ]);
    const badges = screen.getAllByText('next');
    expect(badges).toHaveLength(1);
    expect((badges[0].closest('a') as HTMLElement).textContent).toContain('!7 gl mr');
  });

  it('click calls preventDefault and routes through safeOpen', async () => {
    await renderPanel([todo({ platform: 'github', pr_number: 9, pr_title: 'click me', queue_position: 1 })]);
    const card = screen.getByText('#9 click me').closest('a') as HTMLElement;
    // fireEvent returns false when the event was default-prevented.
    expect(fireEvent.click(card)).toBe(false);
    expect(safeOpen).toHaveBeenCalledTimes(1);
    expect(safeOpen).toHaveBeenCalledWith('https://github.com/o/r/pull/1');
  });

  it('only renders http(s) URLs in href, else "#"', async () => {
    await renderPanel([
      todo({ platform: 'github', pr_number: 1, pr_title: 'ok', target_url: 'https://github.com/o/r/pull/1', queue_position: 1 }),
      todo({ platform: 'github', pr_number: 2, pr_title: 'evil', target_url: 'javascript:alert(1)', queue_position: 2 }),
      todo({ platform: 'github', pr_number: 3, pr_title: 'empty', target_url: '', queue_position: 3 }),
    ]);
    expect(screen.getByText('#1 ok').closest('a')?.getAttribute('href')).toBe('https://github.com/o/r/pull/1');
    expect(screen.getByText('#2 evil').closest('a')?.getAttribute('href')).toBe('#');
    expect(screen.getByText('#3 empty').closest('a')?.getAttribute('href')).toBe('#');
  });

  it('never renders a bare "#" when the number is missing', async () => {
    await renderPanel([
      todo({ platform: 'github', pr_title: 'title only', queue_position: 1 }),
      todo({ platform: 'github', queue_position: 2 }),
    ]);
    expect(screen.getByText('title only')).toBeTruthy();
    expect(screen.getByText('Queued Item')).toBeTruthy();
    expect(screen.queryByText('#')).toBeNull();
    expect(screen.queryByText('# title only')).toBeNull();
  });

  it('renders GitHub and GitLab sections with platform-specific prefixes', async () => {
    await renderPanel([
      todo({ mr_iid: 5, mr_title: 'gl thing', action: 'assigned', project_path: 'g/p', target_url: 'https://gitlab.com/g/p/-/merge_requests/5' }),
      todo({ platform: 'github', pr_number: 6, pr_title: 'gh pr', queue_position: 1 }),
      todo({ platform: 'github', issue_number: 7, issue_title: 'gh issue', queue_position: 2, target_url: 'https://github.com/o/r/issues/7' }),
    ]);
    expect(screen.getByText('GitLab')).toBeTruthy();
    expect(screen.getByText('GitHub Queued')).toBeTruthy();
    expect(screen.getByText('!5 gl thing')).toBeTruthy();
    expect(screen.getByText('#6 gh pr')).toBeTruthy();
    expect(screen.getByText('#7 gh issue')).toBeTruthy();
    expect(screen.getByText('Q#1')).toBeTruthy();
  });

  it('omits the GitLab section header when only GitHub items exist', async () => {
    await renderPanel([todo({ platform: 'github', pr_number: 1, queue_position: 1 })]);
    expect(screen.queryByText('GitLab')).toBeNull();
    expect(screen.getByText('GitHub Queued')).toBeTruthy();
  });
});
