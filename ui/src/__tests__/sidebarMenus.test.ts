// BlackBoard/ui/src/__tests__/sidebarMenus.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { agentMenuItems, eventMenuItems, hhMenuItems, kargoStageMenuItems } from '../components/ops/sidebarMenus';
import type { AgentRegistryEntry, KargoStageStatus } from '../api/types';
import type { HeadhunterTodo } from '../api/client';

beforeEach(() => {
  vi.clearAllMocks();
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
  });

  it('excludes MR link for non-headhunter events', () => {
    const evt = { id: 'evt-2', status: 'active', source: 'chat' };
    const items = eventMenuItems(evt, vi.fn(), vi.fn(), true);
    const mrItem = items.find(i => i.id === 'open-mr');
    expect(mrItem).toBeUndefined();
  });
});

describe('hhMenuItems', () => {
  it('returns open and copy items using safeOpen', () => {
    vi.stubGlobal('open', vi.fn());
    const todo = { todo_id: 1, target_url: 'https://gitlab.com/mr/5', mr_iid: 5, mr_title: 'test', action: 'merge', pipeline_status: 'success' } as unknown as HeadhunterTodo;
    const items = hhMenuItems(todo);
    expect(items[0].id).toBe('open');
    expect(items.find(i => i.id === 'copy')).toBeDefined();
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
