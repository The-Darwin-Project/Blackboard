// BlackBoard/ui/src/api/client.test.ts
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, approveEvent } from './client';

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
