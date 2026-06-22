// BlackBoard/ui/src/__tests__/resolveStreamTarget.test.ts
import { describe, expect, it } from 'vitest';
import { resolveStreamTarget } from '../contexts/OpsStateContext';
import type { AgentRegistryEntry, ActiveEvent } from '../api/types';

function makeAgent(overrides: Partial<AgentRegistryEntry> = {}): AgentRegistryEntry {
  return {
    agent_id: 'test-agent',
    role: '',
    busy: false,
    current_event_id: null,
    current_task_id: null,
    connected_at: Date.now(),
    cli: 'gemini',
    model: 'flash',
    ephemeral: true,
    ...overrides,
  };
}

function makeEvent(overrides: Partial<ActiveEvent> = {}): ActiveEvent {
  return {
    id: 'evt-1',
    source: 'chat',
    service: 'test-svc',
    status: 'active',
    reason: 'test',
    evidence: {
      display_text: 'test',
      source_type: 'chat',
      domain: 'complicated',
      severity: 'info',
    },
    turns: 1,
    created: new Date().toISOString(),
    ...overrides,
  };
}

describe('resolveStreamTarget', () => {
  // ---------------------------------------------------------------------------
  // Core routing (8 cases)
  // ---------------------------------------------------------------------------
  describe('core routing', () => {
    it('routes internal agent (architect) on chat event to agent', () => {
      expect(resolveStreamTarget('architect', 'evt-1', 'chat')).toBe('agent');
    });

    it('routes internal agent (architect) on headhunter event to agent (agent-first)', () => {
      expect(resolveStreamTarget('architect', 'evt-1', 'headhunter')).toBe('agent');
    });

    it('routes non-internal actor on nightwatcher event to ephemeral', () => {
      expect(resolveStreamTarget('oncall-abc', 'evt-1', 'nightwatcher')).toBe('ephemeral');
    });

    it('routes security_analyst on chat event with ephemeral ref match to ephemeral', () => {
      const agents = [makeAgent({ bound_event_id: 'evt-1' })];
      expect(resolveStreamTarget('security_analyst', 'evt-1', 'chat', '', agents)).toBe('ephemeral');
    });

    it('drops security_analyst on chat event without ephemeral ref match', () => {
      expect(resolveStreamTarget('security_analyst', 'evt-1', 'chat')).toBe('drop');
    });

    it('drops unknown actor on unknown source', () => {
      expect(resolveStreamTarget('mystery', 'evt-1', 'aligner')).toBe('drop');
    });

    it('routes nw-sweep prefix event to ephemeral', () => {
      expect(resolveStreamTarget('oncall-xyz', 'nw-sweep-abc', 'nightwatcher')).toBe('ephemeral');
    });

    it('routes kargo_stage subject_type to ephemeral', () => {
      expect(resolveStreamTarget('oncall-xyz', 'evt-1', 'aligner', 'kargo_stage')).toBe('ephemeral');
    });
  });

  // ---------------------------------------------------------------------------
  // Oncall collision cases (3 — Run #3 C)
  // ---------------------------------------------------------------------------
  describe('oncall collision', () => {
    it('routes oncall sysadmin (current_role match via bound_event_id) to ephemeral', () => {
      const agents = [makeAgent({
        role: '',
        current_role: 'sysadmin',
        bound_event_id: 'evt-hh-1',
      })];
      expect(resolveStreamTarget('sysadmin', 'evt-hh-1', 'headhunter', '', agents)).toBe('ephemeral');
    });

    it('routes oncall sysadmin (current_role match via current_event_id) to ephemeral', () => {
      const agents = [makeAgent({
        role: '',
        current_role: 'sysadmin',
        bound_event_id: null,
        current_event_id: 'evt-hh-1',
      })];
      expect(resolveStreamTarget('sysadmin', 'evt-hh-1', 'headhunter', '', agents)).toBe('ephemeral');
    });

    it('routes to agent when bound ephemeral has current_role mismatch', () => {
      const agents = [makeAgent({
        role: '',
        current_role: 'developer',
        bound_event_id: 'evt-hh-1',
      })];
      expect(resolveStreamTarget('sysadmin', 'evt-hh-1', 'headhunter', '', agents)).toBe('agent');
    });

    it('routes permanent sysadmin on HH event (no bound ephemeral) to agent', () => {
      expect(resolveStreamTarget('sysadmin', 'evt-hh-1', 'headhunter')).toBe('agent');
    });
  });

  // ---------------------------------------------------------------------------
  // Edge cases (4)
  // ---------------------------------------------------------------------------
  describe('edge cases', () => {
    it('routes internal agent with falsy evtId (empty string) to agent', () => {
      expect(resolveStreamTarget('architect', '', 'chat')).toBe('agent');
    });

    it('drops non-internal actor on chat event when activeEvents is undefined', () => {
      expect(
        resolveStreamTarget('oncall-x', 'evt-1', 'chat', '', [], undefined)
      ).toBe('drop');
    });

    it('drops brain actor on chat event', () => {
      expect(resolveStreamTarget('brain', 'evt-1', 'chat')).toBe('drop');
    });

    it('routes internal agent on nw-sweep event (no bound ephemeral) to agent', () => {
      expect(resolveStreamTarget('sysadmin', 'nw-sweep-abc', 'nightwatcher')).toBe('agent');
    });
  });

  // ---------------------------------------------------------------------------
  // Fallback detection (2 — Run #3 A)
  // ---------------------------------------------------------------------------
  describe('fallback detection', () => {
    it('routes to ephemeral when activeEvents has headhunter source (no registry match)', () => {
      const events = [makeEvent({ id: 'evt-hh-2', source: 'headhunter' })];
      expect(resolveStreamTarget('oncall-x', 'evt-hh-2', 'aligner', '', [], events)).toBe('ephemeral');
    });

    it('routes timekeeper source event to ephemeral', () => {
      expect(resolveStreamTarget('oncall-x', 'evt-1', 'timekeeper')).toBe('ephemeral');
    });

    it('routes kargo_stage via activeEvents fallback to ephemeral', () => {
      const events = [makeEvent({ id: 'evt-k1', source: 'aligner', subject_type: 'kargo_stage' })];
      expect(resolveStreamTarget('oncall-x', 'evt-k1', 'aligner', '', [], events)).toBe('ephemeral');
    });
  });

  // ---------------------------------------------------------------------------
  // Turn handler + role fallback (2 — Run #4 B)
  // ---------------------------------------------------------------------------
  describe('turn handler + role fallback', () => {
    it('routes bound oncall sysadmin with empty event_source/subject_type to ephemeral', () => {
      const agents = [makeAgent({
        role: '',
        current_role: 'sysadmin',
        bound_event_id: 'evt-hh-1',
      })];
      expect(resolveStreamTarget('sysadmin', 'evt-hh-1', '', '', agents)).toBe('ephemeral');
    });

    it('routes via role fallback when current_role is null', () => {
      const agents = [makeAgent({
        role: 'sysadmin',
        current_role: null,
        bound_event_id: 'evt-hh-1',
      })];
      expect(resolveStreamTarget('sysadmin', 'evt-hh-1', '', '', agents)).toBe('ephemeral');
    });
  });
});
