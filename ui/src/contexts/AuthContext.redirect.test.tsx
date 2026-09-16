// BlackBoard/ui/src/contexts/AuthContext.redirect.test.tsx
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, act, cleanup } from '@testing-library/react';
import { AuthProvider, useAuth } from './AuthContext';
import * as apiClient from '../api/client';

const mockSigninRedirect = vi.fn();
const mockSigninRedirectCallback = vi.fn();
const mockGetUser = vi.fn();

vi.mock('oidc-client-ts', () => {
  let fakeUserManagerInstance: any = null;
  class FakeUserManager {
    constructor() { (window as any).fakeUserManagerInstance = this; }
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
    signinSilent = vi.fn();
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

  it('scenario 3d: same-origin absolute URL with a "//evil.com" path is neutralized to a single-slash path', async () => {
    vi.spyOn(apiClient, 'getConfig').mockResolvedValue(AUTH_ENABLED_CONFIG);
    setLocation('/callback');
    mockSigninRedirectCallback.mockResolvedValue({ state: `${window.location.origin}//evil.com` });

    render(<AuthProvider><Probe /></AuthProvider>);

    await waitFor(() => expect(screen.getByTestId('redirect').textContent).toBe('/evil.com'));
    expect(window.location.pathname).toBe('/evil.com');
    expect(window.location.pathname.startsWith('//')).toBe(false);
  });

  it('scenario 3e: unparseable state falls back to "/" and logs the error', async () => {
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    const urlSpy = vi.spyOn(global, 'URL').mockImplementation(() => {
      throw new TypeError('Invalid URL');
    });
    vi.spyOn(apiClient, 'getConfig').mockResolvedValue(AUTH_ENABLED_CONFIG);
    setLocation('/callback');
    mockSigninRedirectCallback.mockResolvedValue({ state: '/reports?id=xyz' });

    render(<AuthProvider><Probe /></AuthProvider>);

    await waitFor(() => expect(screen.getByTestId('redirect').textContent).toBe('/'));
    expect(consoleErrorSpy).toHaveBeenCalledWith('[Auth] Failed to parse redirect target:', expect.any(TypeError));

    urlSpy.mockRestore();
  });

  it('scenario 3f: hash fragment round-trips through the reconstructed target', async () => {
    vi.spyOn(apiClient, 'getConfig').mockResolvedValue(AUTH_ENABLED_CONFIG);
    setLocation('/callback');
    mockSigninRedirectCallback.mockResolvedValue({ state: '/reports?id=xyz#section-2' });

    render(<AuthProvider><Probe /></AuthProvider>);

    await waitFor(() => expect(screen.getByTestId('redirect').textContent).toBe('/reports?id=xyz#section-2'));
  });

  it('scenario 3g: non-string state falls back to "/"', async () => {
    vi.spyOn(apiClient, 'getConfig').mockResolvedValue(AUTH_ENABLED_CONFIG);
    setLocation('/callback');
    mockSigninRedirectCallback.mockResolvedValue({ state: { nested: 'object' } });

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


function RenewProbe() {
  const { isLoading, isAuthenticated, user, isRenewing, renewToken } = useAuth();
  if (isLoading) return <div>loading</div>;
  return (
    <div>
      <div data-testid="authed">{String(isAuthenticated)}</div>
      <div data-testid="user">{user?.profile?.email || 'none'}</div>
      <div data-testid="renewing">{String(isRenewing)}</div>
      <button onClick={renewToken}>renew</button>
    </div>
  );
}

describe('AuthContext token renewal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.spyOn(apiClient, 'getConfig').mockResolvedValue(AUTH_ENABLED_CONFIG as any); //
    mockGetUser.mockResolvedValue({ access_token: 'valid-token', profile: { email: 'test@example.com' } });
  });

  afterEach(() => {
    vi.useRealTimers();
    cleanup();
  });

  it('onAccessTokenExpired sets isRenewing=true without clearing user', async () => {
    render(
      <AuthProvider>
        <RenewProbe />
      </AuthProvider>
    );
    
    await waitFor(() => {
      expect(screen.getByTestId('authed').textContent).toBe('true');
    });
    
    const mgr = (window as any).fakeUserManagerInstance;
    const expiredCallback = mgr.events.addAccessTokenExpired.mock.calls[0][0];
    
    act(() => {
      expiredCallback();
    });
    
    expect(screen.getByTestId('renewing').textContent).toBe('true');
    expect(screen.getByTestId('authed').textContent).toBe('true');
    expect(screen.getByTestId('user').textContent).toBe('test@example.com');
  });

  it('onUserLoaded clears isRenewing', async () => {
    render(
      <AuthProvider>
        <RenewProbe />
      </AuthProvider>
    );
    
    await waitFor(() => {
      expect(screen.getByTestId('authed').textContent).toBe('true');
    });
    
    const mgr = (window as any).fakeUserManagerInstance;
    const expiredCallback = mgr.events.addAccessTokenExpired.mock.calls[0][0];
    const loadedCallback = mgr.events.addUserLoaded.mock.calls[0][0];
    
    act(() => {
      expiredCallback();
    });
    expect(screen.getByTestId('renewing').textContent).toBe('true');
    
    act(() => {
      loadedCallback({ access_token: 'new-token', profile: { email: 'test@example.com' } });
    });
    expect(screen.getByTestId('renewing').textContent).toBe('false');
  });

  it('onSilentRenewError clears isRenewing and falls back to setUser(null)', async () => {
    render(
      <AuthProvider>
        <RenewProbe />
      </AuthProvider>
    );
    
    await waitFor(() => {
      expect(screen.getByTestId('authed').textContent).toBe('true');
    });
    
    const mgr = (window as any).fakeUserManagerInstance;
    const expiredCallback = mgr.events.addAccessTokenExpired.mock.calls[0][0];
    const errorCallback = mgr.events.addSilentRenewError.mock.calls[0][0];
    
    act(() => {
      expiredCallback();
    });
    
    // Mock getUser to return null to simulate expired token
    mockGetUser.mockResolvedValue(null);
    
    await act(async () => {
      errorCallback(new Error('renew failed'));
    });
    
    expect(screen.getByTestId('renewing').textContent).toBe('false');
    expect(screen.getByTestId('authed').textContent).toBe('false');
    expect(screen.getByTestId('user').textContent).toBe('none');
  });

  it('20s safety timeout flips isRenewing back to false', async () => {
    render(
      <AuthProvider>
        <RenewProbe />
      </AuthProvider>
    );
    
    await waitFor(() => {
      expect(screen.getByTestId('authed').textContent).toBe('true');
    });
    
    const mgr = (window as any).fakeUserManagerInstance;
    const expiredCallback = mgr.events.addAccessTokenExpired.mock.calls[0][0];
    
    act(() => {
      expiredCallback();
    });
    
    expect(screen.getByTestId('renewing').textContent).toBe('true');
    
    await act(async () => {
      vi.advanceTimersByTime(20000);
    });
    
    expect(screen.getByTestId('renewing').textContent).toBe('false');
    // Assert getUser was called again as a re-check
    expect(mockGetUser).toHaveBeenCalled();
  });

  it('renewToken dedups concurrent calls', async () => {
    render(
      <AuthProvider>
        <RenewProbe />
      </AuthProvider>
    );
    
    await waitFor(() => {
      expect(screen.getByTestId('authed').textContent).toBe('true');
    });
    
    const mgr = (window as any).fakeUserManagerInstance;
    
    act(() => {
      screen.getByText('renew').click();
      screen.getByText('renew').click();
    });
    
    expect(mgr.signinSilent).toHaveBeenCalledTimes(1);
  });
});

