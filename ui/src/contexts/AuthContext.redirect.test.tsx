// BlackBoard/ui/src/contexts/AuthContext.redirect.test.tsx
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, act, cleanup } from '@testing-library/react';
import { AuthProvider, useAuth } from './AuthContext';
import * as apiClient from '../api/client';

const mockSigninRedirect = vi.fn();
const mockSigninRedirectCallback = vi.fn();
const mockGetUser = vi.fn();

vi.mock('oidc-client-ts', () => {
  class FakeUserManager {
    events = {
      addUserLoaded: vi.fn(),
      addUserUnloaded: vi.fn(),
      addAccessTokenExpired: vi.fn(),
      addSilentRenewError: vi.fn(),
      removeUserLoaded: vi.fn(),
      removeUserUnloaded: vi.fn(),
      removeAccessTokenExpired: vi.fn(),
      removeSilentRenewError: vi.fn(),
    };
    signinRedirect(...args: unknown[]) { return mockSigninRedirect(...args); }
    signinRedirectCallback(...args: unknown[]) { return mockSigninRedirectCallback(...args); }
    getUser(...args: unknown[]) { return mockGetUser(...args); }
    signoutRedirect = vi.fn();
  }
  return {
    UserManager: FakeUserManager,
    WebStorageStateStore: vi.fn(),
    User: class {},
  };
});

function setLocation(pathname: string, search = '') {
  window.history.pushState({}, '', pathname + search);
}

function Probe() {
  const { isLoading, isAuthenticated, authConfig, postLoginRedirect, login } = useAuth();
  if (isLoading) return <div>loading</div>;
  return (
    <div>
      <div data-testid="authed">{String(isAuthenticated)}</div>
      <div data-testid="config-enabled">{String(authConfig?.enabled)}</div>
      <div data-testid="redirect">{postLoginRedirect}</div>
      <button onClick={login}>login</button>
    </div>
  );
}

const AUTH_ENABLED_CONFIG = {
  contactEmail: 'a@b.com',
  feedbackFormUrl: '',
  appVersion: '1.0.0',
  auth: { enabled: true, issuerUrl: 'https://idp.example.com', clientId: 'client-1' },
};

const AUTH_DISABLED_CONFIG = {
  contactEmail: 'a@b.com',
  feedbackFormUrl: '',
  appVersion: '1.0.0',
  auth: { enabled: false },
};

beforeEach(() => {
  vi.restoreAllMocks();
  mockSigninRedirect.mockReset();
  mockSigninRedirectCallback.mockReset();
  mockGetUser.mockReset();
  mockGetUser.mockResolvedValue(null);
  window.history.pushState({}, '', '/');
});

afterEach(() => {
  cleanup();
});

describe('AuthContext post-login redirect', () => {
  it('scenario 1: share-link deep-link — login() captures /reports?id=xyz as state', async () => {
    vi.spyOn(apiClient, 'getConfig').mockResolvedValue(AUTH_ENABLED_CONFIG);
    setLocation('/reports', '?id=xyz');

    render(<AuthProvider><Probe /></AuthProvider>);
    await waitFor(() => expect(screen.queryByText('login')).not.toBeNull());

    act(() => screen.getByText('login').click());

    expect(mockSigninRedirect).toHaveBeenCalledWith({ state: '/reports?id=xyz' });
  });

  it('scenario 1b: /callback restores the captured deep-link target', async () => {
    vi.spyOn(apiClient, 'getConfig').mockResolvedValue(AUTH_ENABLED_CONFIG);
    setLocation('/callback');
    mockSigninRedirectCallback.mockResolvedValue({ state: '/reports?id=xyz' });

    render(<AuthProvider><Probe /></AuthProvider>);

    await waitFor(() => expect(screen.getByTestId('redirect').textContent).toBe('/reports?id=xyz'));
    expect(window.location.pathname + window.location.search).toBe('/reports?id=xyz');
  });

  it('scenario 2: plain login from root — state is "/"', async () => {
    vi.spyOn(apiClient, 'getConfig').mockResolvedValue(AUTH_ENABLED_CONFIG);
    setLocation('/');

    render(<AuthProvider><Probe /></AuthProvider>);
    await waitFor(() => expect(screen.queryByText('login')).not.toBeNull());

    act(() => screen.getByText('login').click());

    expect(mockSigninRedirect).toHaveBeenCalledWith({ state: '/' });
  });

  it('scenario 3: malicious state (//evil.com) falls back to "/"', async () => {
    vi.spyOn(apiClient, 'getConfig').mockResolvedValue(AUTH_ENABLED_CONFIG);
    setLocation('/callback');
    mockSigninRedirectCallback.mockResolvedValue({ state: '//evil.com' });

    render(<AuthProvider><Probe /></AuthProvider>);

    await waitFor(() => expect(screen.getByTestId('redirect').textContent).toBe('/'));
    expect(window.location.pathname).toBe('/');
  });

  it('scenario 3b: malicious state (/\\evil.com backslash variant) falls back to "/"', async () => {
    vi.spyOn(apiClient, 'getConfig').mockResolvedValue(AUTH_ENABLED_CONFIG);
    setLocation('/callback');
    mockSigninRedirectCallback.mockResolvedValue({ state: '/\\evil.com' });

    render(<AuthProvider><Probe /></AuthProvider>);

    await waitFor(() => expect(screen.getByTestId('redirect').textContent).toBe('/'));
  });

  it('scenario 3c: absolute URL state (https://evil.com) falls back to "/"', async () => {
    vi.spyOn(apiClient, 'getConfig').mockResolvedValue(AUTH_ENABLED_CONFIG);
    setLocation('/callback');
    mockSigninRedirectCallback.mockResolvedValue({ state: 'https://evil.com' });

    render(<AuthProvider><Probe /></AuthProvider>);

    await waitFor(() => expect(screen.getByTestId('redirect').textContent).toBe('/'));
  });

  it('scenario 4: token-expiry re-login on a non-root route returns to that route', async () => {
    vi.spyOn(apiClient, 'getConfig').mockResolvedValue(AUTH_ENABLED_CONFIG);
    setLocation('/incidents');

    render(<AuthProvider><Probe /></AuthProvider>);
    await waitFor(() => expect(screen.queryByText('login')).not.toBeNull());

    act(() => screen.getByText('login').click());

    expect(mockSigninRedirect).toHaveBeenCalledWith({ state: '/incidents' });
  });

  it('scenario 5: auth-disabled mode bypasses the gate, postLoginRedirect unused', async () => {
    vi.spyOn(apiClient, 'getConfig').mockResolvedValue(AUTH_DISABLED_CONFIG);
    setLocation('/');

    render(<AuthProvider><Probe /></AuthProvider>);

    await waitFor(() => expect(screen.getByTestId('config-enabled').textContent).toBe('false'));
    expect(screen.getByTestId('redirect').textContent).toBe('/');
    expect(mockSigninRedirectCallback).not.toHaveBeenCalled();
  });
});
