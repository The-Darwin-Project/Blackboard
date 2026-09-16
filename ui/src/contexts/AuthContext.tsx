// BlackBoard/ui/src/contexts/AuthContext.tsx
// @ai-rules:
// 1. [Pattern]: Fetches /config to discover auth settings. No hardcoded Dex URLs.
// 2. [Pattern]: When auth.enabled=false, isLoading resolves immediately, no login gate.
// 3. [Constraint]: Tokens stored in sessionStorage via oidc-client-ts (survives refresh, cleared on tab close).
// 4. [Pattern]: Three-layer defense-in-depth for token expiry:
//    Layer 1 (OIDC events): addAccessTokenExpired sets isRenewing=true WITHOUT nulling user.
//      Only addSilentRenewError (genuinely dead token) or confirmed 401 terminates session.
//    Layer 2 (401 interceptor): fetchApi 401 → onUnauthorized → logout() (only when user.expired).
//    Layer 3 (WS 4001): server rejects WS → getWSAuthFailureCallback → logout() (full IdP session cleanup).
// 5. [Design]: 20s safety timeout prevents permanent isRenewing=true if IdP iframe hangs.
// 6. [Design]: renewToken() is exported for manual silent renewal (dedup'd against automaticSilentRenew).
// 7. [Design]: isRenewing cleared on BOTH addUserLoaded (happy path) and addSilentRenewError (failure path).
// 8. [Design]: sanitizeRedirectTarget validates via URL parsing + strict origin comparison rather than a
//    prefix blocklist, because prefix checks are brittle against parser-differential bypasses.
import { createContext, useContext, useEffect, useState, useCallback, useMemo, useRef, type ReactNode } from 'react';
import { UserManager, User, WebStorageStateStore } from 'oidc-client-ts';
import { getConfig, setTokenGetter, setOnUnauthorized, setWSAuthFailureCallback } from '../api/client';
import type { AuthConfig } from '../api/types';

export interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  isRenewing: boolean;
  authConfig: AuthConfig | null;
  postLoginRedirect: string;
  login: () => void;
  logout: () => void;
  getAccessToken: () => string | null;
  renewToken: () => Promise<User | null>;
}

const AuthContext = createContext<AuthState>({
  user: null,
  isAuthenticated: false,
  isLoading: true,
  isRenewing: false,
  authConfig: null,
  postLoginRedirect: '/',
  login: () => {},
  logout: () => {},
  getAccessToken: () => null,
  renewToken: () => Promise.resolve(null),
});

let _userManager: UserManager | null = null;

function sanitizeRedirectTarget(raw: string): string {
  try {
    const url = new URL(raw, window.location.origin);
    if (url.origin === window.location.origin) {
      const pathname = url.pathname.replace(/^\/+/, '/');
      return pathname + url.search + url.hash;
    }
  } catch (err) {
    console.error('[Auth] Failed to parse redirect target:', err);
  }
  return '/';
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRenewing, setIsRenewing] = useState(false);
  const [authConfig, setAuthConfig] = useState<AuthConfig | null>(null);
  const [postLoginRedirect, setPostLoginRedirect] = useState('/');
  const renewalTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const renewingRef = useRef(false);

  useEffect(() => {
    let cancelled = false;
    let onUserLoaded: ((u: User) => void) | undefined;
    let onUserUnloaded: (() => void) | undefined;
    let onAccessTokenExpired: (() => void) | undefined;
    let onSilentRenewError: ((err: Error) => Promise<void>) | undefined;

    const clearRenewalTimeout = () => {
      if (renewalTimeoutRef.current) {
        clearTimeout(renewalTimeoutRef.current);
        renewalTimeoutRef.current = null;
      }
    };

    (async () => {
      try {
        const config = await getConfig();
        const auth = config.auth ?? { enabled: false };

        if (cancelled) return;
        setAuthConfig(auth);

        if (!auth.enabled || !auth.issuerUrl || !auth.clientId) {
          setIsLoading(false);
          return;
        }

        const mgr = new UserManager({
          authority: auth.issuerUrl,
          client_id: auth.clientId,
          redirect_uri: `${window.location.origin}/callback`,
          post_logout_redirect_uri: window.location.origin,
          response_type: 'code',
          scope: 'openid profile email groups',
          automaticSilentRenew: true,
          userStore: new WebStorageStateStore({ store: window.sessionStorage }),
        });
        _userManager = mgr;

        onUserLoaded = (u: User) => {
          if (cancelled) return;
          clearRenewalTimeout();
          setIsRenewing(false);
          renewingRef.current = false;
          setUser(u);
        };
        onUserUnloaded = () => { if (!cancelled) setUser(null); };
        onAccessTokenExpired = () => {
          if (cancelled) return;
          console.warn('[Auth] Token expired -- marking isRenewing (automaticSilentRenew in progress)');
          setIsRenewing(true);
          renewingRef.current = true;
          // 20s safety timeout: if renewal doesn't complete, verify session
          clearRenewalTimeout();
          renewalTimeoutRef.current = setTimeout(async () => {
            if (cancelled) return;
            console.warn('[Auth] 20s renewal timeout -- verifying session');
            setIsRenewing(false);
            renewingRef.current = false;
            try {
              const current = await mgr.getUser();
              if (!cancelled && (!current || current.expired)) {
                console.warn('[Auth] Session expired after renewal timeout');
                setUser(null);
              }
            } catch {
              if (!cancelled) setUser(null);
            }
          }, 20_000);
        };
        onSilentRenewError = async (err: Error) => {
          if (cancelled) return;
          console.error('[Auth] Silent renew failed:', err);
          clearRenewalTimeout();
          setIsRenewing(false);
          renewingRef.current = false;
          const current = await mgr.getUser();
          if (!cancelled && (!current || current.expired)) setUser(null);
        };

        mgr.events.addUserLoaded(onUserLoaded);
        mgr.events.addUserUnloaded(onUserUnloaded);
        mgr.events.addAccessTokenExpired(onAccessTokenExpired);
        mgr.events.addSilentRenewError(onSilentRenewError);

        if (window.location.pathname === '/callback') {
          try {
            const u = await mgr.signinRedirectCallback();
            const raw = typeof u.state === 'string' ? u.state : '/';
            const target = sanitizeRedirectTarget(raw);
            if (!cancelled) {
              window.history.replaceState({}, '', target);
              setUser(u);
              setPostLoginRedirect(target);
            }
          } catch (err) {
            console.error('[Auth] Callback error:', err);
          }
        } else {
          const existing = await mgr.getUser();
          if (!cancelled && existing && !existing.expired) {
            setUser(existing);
          }
        }
      } catch (err) {
        console.error('[Auth] Init failed:', err);
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();

    return () => {
      cancelled = true;
      clearRenewalTimeout();
      if (_userManager) {
        if (onUserLoaded) _userManager.events.removeUserLoaded(onUserLoaded);
        if (onUserUnloaded) _userManager.events.removeUserUnloaded(onUserUnloaded);
        if (onAccessTokenExpired) _userManager.events.removeAccessTokenExpired(onAccessTokenExpired);
        if (onSilentRenewError) _userManager.events.removeSilentRenewError(onSilentRenewError);
      }
    };
  }, []);

  const login = useCallback(() => {
    _userManager?.signinRedirect({ state: window.location.pathname + window.location.search });
  }, []);

  const logout = useCallback(() => {
    _userManager?.signoutRedirect();
  }, []);

  const getAccessToken = useCallback(() => {
    return user?.access_token ?? null;
  }, [user]);

  const renewToken = useCallback(async (): Promise<User | null> => {
    if (!_userManager) return null;
    // Dedup against an in-flight automaticSilentRenew
    if (renewingRef.current) {
      console.log('[Auth] renewToken: already renewing, waiting for completion');
      return _userManager.getUser();
    }
    try {
      renewingRef.current = true;
      setIsRenewing(true);
      const u = await _userManager.signinSilent();
      // onUserLoaded will fire and clear isRenewing
      return u;
    } catch (err) {
      console.error('[Auth] Manual renewToken failed:', err);
      renewingRef.current = false;
      setIsRenewing(false);
      return null;
    }
  }, []);

  useEffect(() => {
    setTokenGetter(getAccessToken);
  }, [getAccessToken]);

  const onUnauthorized = useCallback(() => {
    if (user?.expired) logout();
  }, [user, logout]);

  useEffect(() => {
    setOnUnauthorized(onUnauthorized);
    return () => setOnUnauthorized(null);
  }, [onUnauthorized]);

  useEffect(() => {
    setWSAuthFailureCallback(logout);
    return () => setWSAuthFailureCallback(null);
  }, [logout]);

  const value = useMemo(() => ({
    user,
    isAuthenticated: !!user && !user.expired,
    isLoading,
    isRenewing,
    authConfig,
    postLoginRedirect,
    login,
    logout,
    getAccessToken,
    renewToken,
  }), [user, isLoading, isRenewing, authConfig, postLoginRedirect, login, logout, getAccessToken, renewToken]);

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
