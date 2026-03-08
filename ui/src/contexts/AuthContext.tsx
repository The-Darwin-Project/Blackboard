// BlackBoard/ui/src/contexts/AuthContext.tsx
// @ai-rules:
// 1. [Pattern]: Fetches /config to discover auth settings. No hardcoded Dex URLs.
// 2. [Pattern]: When auth.enabled=false, isLoading resolves immediately, no login gate.
// 3. [Constraint]: Tokens stored in sessionStorage via oidc-client-ts (survives refresh, cleared on tab close).
import { createContext, useContext, useEffect, useState, useCallback, type ReactNode } from 'react';
import { UserManager, User, WebStorageStateStore } from 'oidc-client-ts';
import { getConfig, setTokenGetter } from '../api/client';
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

        mgr.events.addUserLoaded((u) => { if (!cancelled) setUser(u); });
        mgr.events.addUserUnloaded(() => { if (!cancelled) setUser(null); });
        mgr.events.addSilentRenewError((err) => {
          console.error('[Auth] Silent renew failed:', err);
        });

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

    return () => { cancelled = true; };
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

  return (
    <AuthContext.Provider value={{
      user,
      isAuthenticated: !!user && !user.expired,
      isLoading,
      authConfig,
      login,
      logout,
      getAccessToken,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
