// BlackBoard/ui/src/__tests__/sidebarMenus.test.ts
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  agentMenuItems,
  eventMenuItems,
  hhMenuItems,
  kargoStageMenuItems,
  formatHeadhunterLabel,
  getHeadhunterItemKey,
  isGitHubTodo,
  isGitHubIssue,
} from '../components/ops/sidebarMenus';
import type { AgentRegistryEntry, KargoStageStatus } from '../api/types';
import type { HeadhunterTodo } from '../api/client';

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('agentMenuItems', () => {
  it('returns focus and info items', () => {
    const setHotspot = vi.fn();
    const items = agentMenuItems('architect', undefined, setHotspot);
    expect(items.length).toBeGreaterThanOrEqual(3);
    expect(items[0].id).toBe('focus');
    items[0].onClick();
    expect(setHotspot).toHaveBeenCalledWith('architect');
  });

  it('copies agent ID via clipboard', () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });
    const reg = { agent_id: 'a-123', role: 'architect', busy: false } as AgentRegistryEntry;
    const items = agentMenuItems('architect', reg, vi.fn());
    const copyItem = items.find(i => i.id === 'copy');
    copyItem?.onClick();
    expect(writeText).toHaveBeenCalledWith('a-123');
  });
});

describe('eventMenuItems', () => {
  it('includes MR link when source is headhunter with gitlab_context', () => {
    const selectEvent = vi.fn();
    const send = vi.fn();
    const evt = {
      id: 'evt-1', status: 'active', source: 'headhunter',
      evidence: { gitlab_context: { target_url: 'https://gitlab.com/mr/1' } },
    };
    const items = eventMenuItems(evt, selectEvent, send, true);
    const mrItem = items.find(i => i.id === 'open-mr');
    expect(mrItem).toBeDefined();
    expect(mrItem?.label).toBe('Open MR in GitLab');
  });

  it('excludes MR link for non-headhunter events', () => {
    const evt = { id: 'evt-2', status: 'active', source: 'chat' };
    const items = eventMenuItems(evt, vi.fn(), vi.fn(), true);
    const mrItem = items.find(i => i.id === 'open-mr');
    expect(mrItem).toBeUndefined();
  });

  // T-5: Event menu GitHub PR context
  it('includes PR link when source is headhunter with github_context (T-5)', () => {
    const evt = {
      id: 'evt-gh-pr',
      status: 'active',
      source: 'headhunter',
      evidence: { github_context: { pr_url: 'https://github.com/o/r/pull/1' } },
    };
    const items = eventMenuItems(evt, vi.fn(), vi.fn(), true);
    const prItem = items.find(i => i.id === 'open-mr');
    expect(prItem).toBeDefined();
    expect(prItem?.label).toBe('Open PR in GitHub');
  });

  // T-6: Event menu GitHub Issue context
  it('includes Issue link when source is headhunter with github_issue_context (T-6)', () => {
    const evt = {
      id: 'evt-gh-issue',
      status: 'active',
      source: 'headhunter',
      evidence: { github_issue_context: { html_url: 'https://github.com/o/r/issues/2' } },
    };
    const items = eventMenuItems(evt, vi.fn(), vi.fn(), true);
    const issueItem = items.find(i => i.id === 'open-mr');
    expect(issueItem).toBeDefined();
    expect(issueItem?.label).toBe('Open Issue in GitHub');
  });

  it('identifies GitHub issue when evidence has target_url with /issues/', () => {
    const evt = {
      id: 'evt-gh-issues-url',
      status: 'active',
      source: 'headhunter',
      evidence: { target_url: 'https://github.com/o/r/issues/42' },
    };
    const items = eventMenuItems(evt, vi.fn(), vi.fn(), true);
    const issueItem = items.find(i => i.id === 'open-mr');
    expect(issueItem).toBeDefined();
    expect(issueItem?.label).toBe('Open Issue in GitHub');
  });
});

describe('isGitHubTodo', () => {
  it('returns true when platform is explicitly "github"', () => {
    expect(isGitHubTodo({ platform: 'github' } as HeadhunterTodo)).toBe(true);
  });

  it('returns true when pr_number or issue_number is present', () => {
    expect(isGitHubTodo({ pr_number: 10 } as HeadhunterTodo)).toBe(true);
    expect(isGitHubTodo({ issue_number: 20 } as HeadhunterTodo)).toBe(true);
  });

  it('returns true when target_url includes github.com', () => {
    expect(isGitHubTodo({ target_url: 'https://github.com/org/repo/pull/1' } as HeadhunterTodo)).toBe(true);
  });

  it('returns false when platform is "gitlab" or gitlab indicators', () => {
    expect(isGitHubTodo({ platform: 'gitlab', mr_iid: 1 } as HeadhunterTodo)).toBe(false);
    expect(isGitHubTodo({ target_url: 'https://gitlab.com/org/repo/-/merge_requests/1' } as HeadhunterTodo)).toBe(false);
    expect(isGitHubTodo({} as HeadhunterTodo)).toBe(false);
  });
});

describe('isGitHubIssue', () => {
  it('returns true when issue_number is set on github item', () => {
    expect(isGitHubIssue({ platform: 'github', issue_number: 42 } as HeadhunterTodo)).toBe(true);
    expect(isGitHubIssue({ issue_number: 42 } as HeadhunterTodo)).toBe(true);
  });

  it('returns true when target_url contains /issues/ on github item', () => {
    expect(isGitHubIssue({ target_url: 'https://github.com/org/repo/issues/42' } as HeadhunterTodo)).toBe(true);
  });

  it('returns false for github PRs', () => {
    expect(isGitHubIssue({ platform: 'github', pr_number: 42, target_url: 'https://github.com/org/repo/pull/42' } as HeadhunterTodo)).toBe(false);
  });

  it('returns false for gitlab items', () => {
    expect(isGitHubIssue({ platform: 'gitlab', mr_iid: 42, target_url: 'https://gitlab.com/org/repo/-/issues/42' } as HeadhunterTodo)).toBe(false);
  });
});

describe('hhMenuItems', () => {
  // Existing test preserved
  it('returns open and copy items using safeOpen', () => {
    vi.stubGlobal('open', vi.fn());
    const todo = { todo_id: 1, target_url: 'https://gitlab.com/mr/5', mr_iid: 5, mr_title: 'test', action: 'merge', pipeline_status: 'success' } as unknown as HeadhunterTodo;
    const items = hhMenuItems(todo);
    expect(items[0].id).toBe('open');
    expect(items.find(i => i.id === 'copy')).toBeDefined();
  });

  // T-1: GitLab MR context menu formatting
  it('formats GitLab MR context menu correctly (T-1)', () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });
    const todo = {
      todo_id: 1,
      target_url: 'https://gitlab.com/mr/1',
      mr_iid: 10,
    } as unknown as HeadhunterTodo;
    const items = hhMenuItems(todo);
    expect(items[0].label).toBe('Open MR in GitLab');
    const copyItem = items.find(i => i.id === 'copy');
    expect(copyItem).toBeDefined();
    expect(copyItem?.label).toBe('Copy MR URL');
    copyItem?.onClick();
    expect(writeText).toHaveBeenCalledWith('https://gitlab.com/mr/1');
  });

  // T-2: GitHub PR context menu formatting
  it('formats GitHub PR context menu correctly (T-2)', () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });
    const todo = {
      platform: 'github',
      pr_number: 101,
      target_url: 'https://github.com/o/r/pull/101',
    } as unknown as HeadhunterTodo;
    const items = hhMenuItems(todo);
    expect(items[0].label).toBe('Open PR in GitHub');
    const copyItem = items.find(i => i.id === 'copy');
    expect(copyItem).toBeDefined();
    expect(copyItem?.label).toBe('Copy PR URL');
    copyItem?.onClick();
    expect(writeText).toHaveBeenCalledWith('https://github.com/o/r/pull/101');
  });

  // T-3: GitHub Issue context menu formatting
  it('formats GitHub Issue context menu correctly (T-3)', () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });
    const todo = {
      platform: 'github',
      issue_number: 202,
      target_url: 'https://github.com/o/r/issues/202',
    } as unknown as HeadhunterTodo;
    const items = hhMenuItems(todo);
    expect(items[0].label).toBe('Open Issue in GitHub');
    const copyItem = items.find(i => i.id === 'copy');
    expect(copyItem).toBeDefined();
    expect(copyItem?.label).toBe('Copy Issue URL');
    copyItem?.onClick();
    expect(writeText).toHaveBeenCalledWith('https://github.com/o/r/issues/202');
  });

  // T-4: Safe external URL opening
  it('calls safeOpen with target_url when opening external item (T-4)', () => {
    const openMock = vi.fn();
    vi.stubGlobal('open', openMock);
    const todo = {
      platform: 'github',
      pr_number: 101,
      target_url: 'https://github.com/o/r/pull/101',
    } as unknown as HeadhunterTodo;
    const items = hhMenuItems(todo);
    items[0].onClick();
    expect(openMock).toHaveBeenCalledWith('https://github.com/o/r/pull/101', '_blank', 'noopener,noreferrer');
  });

  it('handles clipboard write failure gracefully', () => {
    const writeText = vi.fn().mockRejectedValue(new Error('Permission denied'));
    Object.assign(navigator, { clipboard: { writeText } });
    const todo = {
      platform: 'github',
      pr_number: 101,
      target_url: 'https://github.com/o/r/pull/101',
    } as unknown as HeadhunterTodo;
    const items = hhMenuItems(todo);
    const copyItem = items.find(i => i.id === 'copy');
    expect(() => copyItem?.onClick()).not.toThrow();
  });
});

describe('formatHeadhunterLabel', () => {
  // T-7: Sidebar label formatting (GitHub PR)
  it('formats GitHub PR correctly without "!undefined" (T-7)', () => {
    const todo = {
      platform: 'github',
      pr_number: 55,
      pr_title: 'fix something',
    } as unknown as HeadhunterTodo;
    const label = formatHeadhunterLabel(todo);
    expect(label).toBe('#55 fix something');
    expect(label).not.toContain('!undefined');
  });

  // T-8: Sidebar label formatting (GitHub Issue)
  it('formats GitHub Issue correctly (T-8)', () => {
    const todo = {
      platform: 'github',
      issue_number: 77,
      issue_title: 'bug report',
    } as unknown as HeadhunterTodo;
    const label = formatHeadhunterLabel(todo);
    expect(label).toBe('#77 bug report');
    expect(label).not.toContain('!undefined');
  });

  // T-9: Sidebar label fallback (missing title/number)
  it('provides "Queued Item" fallback when title and number are missing (T-9)', () => {
    const todo = {
      platform: 'github',
    } as unknown as HeadhunterTodo;
    const label = formatHeadhunterLabel(todo);
    expect(label).toBe('Queued Item');
    expect(label).not.toContain('!undefined');
  });

  it('formats GitLab MR correctly with "!" prefix', () => {
    const todo = {
      mr_iid: 12,
      mr_title: 'add feature',
    } as unknown as HeadhunterTodo;
    const label = formatHeadhunterLabel(todo);
    expect(label).toBe('!12 add feature');
  });

  it('truncates titles containing emoji surrogate pairs code-point safely', () => {
    const emojiTitle = '🚀'.repeat(40);
    const todo = {
      platform: 'github',
      pr_number: 10,
      pr_title: emojiTitle,
    } as unknown as HeadhunterTodo;
    const label = formatHeadhunterLabel(todo);
    expect(label).toBe(`#10 ${'🚀'.repeat(30)}`);
  });

  it('does not include a trailing space when title is empty', () => {
    const ghTodo = {
      platform: 'github',
      pr_number: 10,
      pr_title: '',
    } as unknown as HeadhunterTodo;
    expect(formatHeadhunterLabel(ghTodo)).toBe('#10');

    const glTodo = {
      mr_iid: 20,
      mr_title: '',
    } as unknown as HeadhunterTodo;
    expect(formatHeadhunterLabel(glTodo)).toBe('!20');
  });
});

describe('getHeadhunterItemKey', () => {
  // T-10: Composite key collision prevention
  it('produces distinct composite keys for GitHub items without todo_id (T-10)', () => {
    const todo1 = {
      platform: 'github',
      pr_number: 1,
      project_path: 'o/r',
    } as unknown as HeadhunterTodo;
    const todo2 = {
      platform: 'github',
      pr_number: 2,
      project_path: 'o/r',
    } as unknown as HeadhunterTodo;
    const key1 = getHeadhunterItemKey(todo1, 0);
    const key2 = getHeadhunterItemKey(todo2, 1);
    expect(key1).toBe('gh-1-o/r-0');
    expect(key2).toBe('gh-2-o/r-1');
    expect(key1).not.toBe(key2);
  });

  it('preserves numeric todo_id when present', () => {
    const todo = {
      todo_id: 99,
      mr_iid: 42,
    } as unknown as HeadhunterTodo;
    expect(getHeadhunterItemKey(todo, 0)).toBe(99);
  });
});

describe('kargoStageMenuItems', () => {
  it('includes create-event item', () => {
    const send = vi.fn();
    const stage: KargoStageStatus = {
      project: 'proj', stage: 'stage-1', promotion: 'promo-1',
      phase: 'Failed', message: '', failed_step: 'verify', service: 'svc', mr_url: '',
    };
    const items = kargoStageMenuItems(stage, send, true);
    const createItem = items.find(i => i.id === 'create-event');
    expect(createItem).toBeDefined();
    expect(createItem?.disabled).toBe(false);
  });

  it('includes MR link when mr_url is present', () => {
    const stage: KargoStageStatus = {
      project: 'proj', stage: 'stage-1', promotion: 'promo-1',
      phase: 'Failed', message: '', failed_step: '', service: 'svc', mr_url: 'https://gitlab.com/mr/99',
    };
    const items = kargoStageMenuItems(stage, vi.fn(), true);
    const mrItem = items.find(i => i.id === 'open-mr');
    expect(mrItem).toBeDefined();
  });
});
