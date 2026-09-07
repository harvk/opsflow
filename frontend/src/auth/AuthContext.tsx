import {
  createContext,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import {
  getCurrentUserRequest,
  loginRequest,
  logoutRequest,
} from "../api/authApi";

import {
  clearAccessToken,
  refreshAccessToken,
  setAccessToken,
} from "../api/apiClient";

import type { AuthUser } from "../types/auth";

/*
 * =========================================================
 * AUTH CONTEXT CONTRACT
 * =========================================================
 */

interface AuthContextValue {
  user: AuthUser | null;

  isAuthenticated: boolean;

  isInitializing: boolean;

  login: (email: string, password: string) => Promise<void>;

  logout: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | undefined>(
  undefined,
);

interface AuthProviderProps {
  children: ReactNode;
}

/*
 * =========================================================
 * AUTH PROVIDER
 * =========================================================
 *
 * React intentionally stores only application identity
 * state here.
 *
 * AuthContext does NOT store:
 *
 *   refresh JWT
 *   CSRF token
 *
 * Refresh JWT:
 *   browser-managed HttpOnly cookie
 *
 * CSRF token:
 *   browser-readable cookie
 *   apiClient copies it into X-CSRF-Token
 *
 * Access JWT:
 *   apiClient module memory only
 */

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<AuthUser | null>(null);

  const [isInitializing, setIsInitializing] = useState(true);

  /*
   * React StrictMode performs additional development
   * lifecycle checks.
   *
   * Do not submit the initial refresh operation twice.
   */
  const hasInitializedRef = useRef(false);

  /*
   * =======================================================
   * LOCAL AUTHENTICATION CLEANUP
   * =======================================================
   *
   * This function does not contact FastAPI.
   *
   * It clears:
   *
   *   in-memory access token
   *   React user state
   */

  const clearLocalAuthentication = useCallback(() => {
    clearAccessToken();

    setUser(null);
  }, []);

  /*
   * =======================================================
   * LOGIN
   * =======================================================
   *
   * Successful login establishes:
   *
   * FastAPI JSON
   *   -> short-lived access JWT
   *
   * browser cookies
   *   -> HttpOnly refresh JWT
   *   -> readable CSRF token
   *
   * React stores only the access JWT in module memory.
   */

  const login = useCallback(
    async (email: string, password: string) => {
      const token = await loginRequest({
        email,
        password,
      });

      setAccessToken(token.access_token);

      try {
        /*
         * Resolve the authoritative user identity using
         * the newly issued bearer access token.
         */
        const authenticatedUser = await getCurrentUserRequest();

        setUser(authenticatedUser);
      } catch (error) {
        /*
         * Login itself succeeded, meaning the browser may
         * already possess its refresh and CSRF cookies.
         *
         * If user resolution fails, attempt to clean that
         * server/browser session up as well.
         */
        try {
          await logoutRequest();
        } catch {
          /*
           * Local logout must still proceed even if the
           * cleanup request itself fails.
           */
        }

        clearLocalAuthentication();

        throw error;
      }
    },
    [clearLocalAuthentication],
  );

  /*
   * =======================================================
   * LOGOUT
   * =======================================================
   *
   * logoutRequest() uses apiFetch().
   *
   * apiFetch supplies:
   *
   *   HttpOnly refresh cookie automatically through fetch
   *   credentials
   *
   *   CSRF cookie automatically through the browser
   *
   *   X-CSRF-Token deliberately through JavaScript
   */

  const logout = useCallback(async () => {
    try {
      await logoutRequest();
    } finally {
      /*
       * The user explicitly requested logout.
       *
       * Local UI authentication state should therefore
       * always end even if the network request itself
       * fails.
       */
      clearLocalAuthentication();
    }
  }, [clearLocalAuthentication]);

  /*
   * =======================================================
   * RESTORE AUTHENTICATION AFTER PAGE LOAD
   * =======================================================
   *
   * A browser reload destroys the in-memory access token.
   *
   * We intentionally never recover access credentials from:
   *
   *   localStorage
   *   sessionStorage
   *   IndexedDB
   *
   * Instead:
   *
   *   refresh cookie
   *   +
   *   CSRF cookie
   *   +
   *   X-CSRF-Token
   *       ↓
   *   POST /auth/refresh
   *       ↓
   *   new access JWT
   */

  useEffect(() => {
    if (hasInitializedRef.current) {
      return;
    }

    hasInitializedRef.current = true;

    async function restoreAuthentication() {
      try {
        /*
         * refreshAccessToken() never reads the refresh JWT.
         *
         * The browser attaches that HttpOnly cookie
         * automatically.
         *
         * apiClient reads only the CSRF cookie and copies
         * its value into X-CSRF-Token.
         */
        const token = await refreshAccessToken();

        if (!token) {
          clearLocalAuthentication();

          return;
        }

        /*
         * A fresh access JWT now exists in apiClient
         * module memory.
         *
         * Resolve the authoritative user.
         */
        const authenticatedUser = await getCurrentUserRequest();

        setUser(authenticatedUser);
      } catch {
        clearLocalAuthentication();
      } finally {
        setIsInitializing(false);
      }
    }

    void restoreAuthentication();
  }, [clearLocalAuthentication]);

  /*
   * =======================================================
   * GLOBAL AUTHENTICATION FAILURE
   * =======================================================
   *
   * apiFetch dispatches opsflow:unauthorized only after:
   *
   * protected request
   *       ↓
   *      401
   *       ↓
   * coordinated refresh attempt
   *       ↓
   * refresh failed
   *
   * The React identity is no longer trustworthy at that
   * point.
   */

  useEffect(() => {
    function handleUnauthorized() {
      clearLocalAuthentication();
    }

    window.addEventListener("opsflow:unauthorized", handleUnauthorized);

    return () => {
      window.removeEventListener("opsflow:unauthorized", handleUnauthorized);
    };
  }, [clearLocalAuthentication]);

  /*
   * =======================================================
   * CONTEXT VALUE
   * =======================================================
   */

  const value = useMemo(
    () => ({
      user,

      isAuthenticated: user !== null,

      isInitializing,

      login,

      logout,
    }),
    [user, isInitializing, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
