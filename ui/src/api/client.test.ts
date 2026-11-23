// BlackBoard/ui/src/api/client.test.ts
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, approveEvent, headhunterItemAction } from './client';

describe('api/client fetchApi & approveEvent (H9)', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('preserves structured ApiError.body and string detail on 409 response', async () => {
    const payload = {
      code: 'sha_drift',
      detail: 'HEAD SHA changed',
      approval_requested_sha: '1111111111111111',
      live_sha: '2222222222222222',
    };
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      new Response(JSON.stringify(payload), {
        status: 409,
        statusText: 'Conflict',
        headers: { 'Content-Type': 'application/json' },
      })
    );

    let caught: unknown;
    try {
      await approveEvent('evt-1');
    } catch (err) {
      caught = err;
    }

    expect(fetchSpy).toHaveBeenCalledWith(
      '/queue/evt-1/approve',
      expect.objectContaining({ method: 'POST' })
    );
    expect(fetchSpy.mock.calls[0][1]).not.toHaveProperty('body');
    expect(caught).toBeInstanceOf(ApiError);
    const apiErr = caught as ApiError;
    expect(apiErr.status).toBe(409);
    expect(apiErr.detail).toBe('HEAD SHA changed');
    expect(apiErr.body).toEqual(payload);
  });

  it('sends expected_sha JSON body when approveEvent receives expectedSha', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      new Response(JSON.stringify({ status: 'approved' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    );

    await approveEvent('evt-2', 'abcdef1234567890');
    expect(fetchSpy).toHaveBeenCalledWith(
      '/queue/evt-2/approve',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ expected_sha: 'abcdef1234567890' }),
      })
    );
  });

  it('handles non-JSON 409 and non-string FastAPI validation detail safely without [object Object]', async () => {
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response('<html>502 Bad Gateway</html>', { status: 409, statusText: 'Conflict' }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: [{ msg: 'Field required' }] }), {
          status: 422,
          statusText: 'Unprocessable Entity',
          headers: { 'Content-Type': 'application/json' },
        })
      );

    await expect(approveEvent('evt-3')).rejects.toMatchObject({
      status: 409,
      detail: undefined,
      body: undefined,
    });

    await expect(approveEvent('evt-4')).rejects.toMatchObject({
      status: 422,
      detail: undefined,
      body: { detail: [{ msg: 'Field required' }] },
    });
  });
});

describe('api/client headhunterItemAction (C1-1, C2-T1)', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  const mockJsonOk = (body: Record<string, unknown> = { ok: true, debounced: false }) =>
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      new Response(JSON.stringify(body), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

  it('sends project_id and strips project_path for GitLab MR', async () => {
    const fetchSpy = mockJsonOk();

    await headhunterItemAction('promote', {
      platform: 'gitlab',
      project_path: 'cnv/release-app',
      project_id: 99,
      item_number: 42,
      is_issue: false,
    });

    expect(fetchSpy).toHaveBeenCalledWith(
      '/queue/headhunter/items/promote',
      expect.objectContaining({ method: 'POST' }),
    );
    const sentBody = JSON.parse(String((fetchSpy.mock.calls[0][1] as RequestInit).body));
    expect(sentBody).toEqual({
      platform: 'gitlab',
      project_id: 99,
      item_number: 42,
      is_issue: false,
    });
    expect(sentBody).not.toHaveProperty('project_path');
  });

  it('falls back to project_path as project_id when project_id is omitted for GitLab MR and strips project_path', async () => {
    const fetchSpy = mockJsonOk();

    await headhunterItemAction('dismiss', {
      platform: 'gitlab',
      project_path: 'cnv/release-app',
      item_number: 42,
      is_issue: false,
    });

    const sentBody = JSON.parse(String((fetchSpy.mock.calls[0][1] as RequestInit).body));
    expect(sentBody).toEqual({
      platform: 'gitlab',
      project_id: 'cnv/release-app',
      item_number: 42,
      is_issue: false,
    });
    expect(sentBody).not.toHaveProperty('project_path');
  });

  it('derives owner and repo from project_path and strips project_path for GitHub PR', async () => {
    const fetchSpy = mockJsonOk();

    await headhunterItemAction('dismiss', {
      platform: 'github',
      project_path: 'org/app',
      item_number: 45,
      is_issue: false,
    });

    expect(fetchSpy).toHaveBeenCalledWith(
      '/queue/headhunter/items/dismiss',
      expect.objectContaining({ method: 'POST' }),
    );
    const sentBody = JSON.parse(String((fetchSpy.mock.calls[0][1] as RequestInit).body));
    expect(sentBody).toEqual({
      platform: 'github',
      owner: 'org',
      repo: 'app',
      item_number: 45,
      is_issue: false,
    });
    expect(sentBody).not.toHaveProperty('project_path');
  });

  it('derives owner and repo, preserves is_issue: true, and strips project_path for GitHub Issue', async () => {
    const fetchSpy = mockJsonOk();

    await headhunterItemAction('requeue', {
      platform: 'github',
      project_path: 'org/issue-repo',
      item_number: 88,
      is_issue: true,
    });

    expect(fetchSpy).toHaveBeenCalledWith(
      '/queue/headhunter/items/requeue',
      expect.objectContaining({ method: 'POST' }),
    );
    const sentBody = JSON.parse(String((fetchSpy.mock.calls[0][1] as RequestInit).body));
    expect(sentBody).toEqual({
      platform: 'github',
      owner: 'org',
      repo: 'issue-repo',
      item_number: 88,
      is_issue: true,
    });
    expect(sentBody).not.toHaveProperty('project_path');
  });
});
