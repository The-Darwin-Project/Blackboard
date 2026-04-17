// BlackBoard/ui/src/contexts/AuthContext.tsx
// @ai-rules:
// 1. [Pattern]: Fetches /config to discover auth settings. No hardcoded Dex URLs.
// 2. [Pattern]: When auth.enabled=false, isLoading resolves immediately, no login gate.
// 3. [Constraint]: Tokens stored in sessionStorage via oidc-client-ts (survives refresh, cleared on tab close).
// 4. [Pattern]: Three-layer defense-in-depth for token expiry (auto-redirects to LoginPage on expiry):
//    Layer 1 (OIDC events): addAccessTokenExpired/addSilentRenewError → setUser(null) → AuthGate shows LoginPage.
//    Layer 2 (401 interceptor): fetchApi 401 → onUnauthorized → logout() (only when user.expired, guards silent-renew race).
//    Layer 3 (WS 4001): server rejects WS → getWSAuthFailureCallback → logout() (full IdP session cleanup).
// 5. [Design]: Layer 1 uses setUser(null) instead of logout()/signoutRedirect(). Both show LoginPage via AuthGate.
//    setUser(null) is preferred because: (a) no network round-trip to Dex during expiry, (b) avoids redirect
//    mid-render, (c) if Dex session is still alive the user re-authenticates quickly on next login click.
//    Full IdP session cleanup (signoutRedirect) is handled by Layer 3 and the manual logout button.
// 6. [Design]: Layer 2 gates logout() on user?.expired to prevent false logout during in-flight silent renew.
//    Edge case: server-side token revocation while client TTL says "not expired" → user stays on broken session
//    until Layer 1 TTL fires or Layer 3 WS 4001 catches it. Accepted: false logout during renewal is worse.
import { createContext, useContext, useEffect, useState, useCallback, useMemo, type ReactNode } from 'react';
import { UserManager, User, WebStorageStateStore } from 'oidc-client-ts';
import { getConfig, setTokenGetter, setOnUnauthorized, setWSAuthFailureCallback } from '../api/client';
import type { AuthConfig } from '../api/types';

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  authConfig: AuthConfig | null;
  login: () => void;
  logout: () => void;
  getAccessToken: () => string | null;
}

const AuthContext = createContext<AuthState>({
  user: null,
  isAuthenticated: false,
  isLoading: true,
  authConfig: null,
  login: () => {},
  logout: () => {},
  getAccessToken: () => null,
});

let _userManager: UserManager | null = null;

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [authConfig, setAuthConfig] = useState<AuthConfig | null>(null);

  useEffect(() => {
    let cancelled = false;
    let onUserLoaded: ((u: User) => void) | undefined;
    let onUserUnloaded: (() => void) | undefined;
    let onAccessTokenExpired: (() => void) | undefined;
    let onSilentRenewError: ((err: Error) => Promise<void>) | undefined;

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

        onUserLoaded = (u: User) => { if (!cancelled) setUser(u); };
        onUserUnloaded = () => { if (!cancelled) setUser(null); };
        onAccessTokenExpired = () => {
          console.warn('[Auth] Token expired');
          if (!cancelled) setUser(null);
        };
        onSilentRenewError = async (err: Error) => {
          console.error('[Auth] Silent renew failed:', err);
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
            if (!cancelled) setUser(u);
            window.history.replaceState({}, '', '/');
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
      if (_userManager) {
        if (onUserLoaded) _userManager.events.removeUserLoaded(onUserLoaded);
        if (onUserUnloaded) _userManager.events.removeUserUnloaded(onUserUnloaded);
        if (onAccessTokenExpired) _userManager.events.removeAccessTokenExpired(onAccessTokenExpired);
        if (onSilentRenewError) _userManager.events.removeSilentRenewError(onSilentRenewError);
      }
    };
  }, []);

  const login = useCallback(() => {
    _userManager?.signinRedirect();
  }, []);

  const logout = useCallback(() => {
    _userManager?.signoutRedirect();
  }, []);

  const getAccessToken = useCallback(() => {
    return user?.access_token ?? null;
  }, [user]);

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
    authConfig,
    login,
    logout,
    getAccessToken,
  }), [user, isLoading, authConfig, login, logout, getAccessToken]);

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
