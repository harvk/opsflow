import {
  createContext,
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { getCurrentUserRequest, loginRequest } from "../api/authApi";

import {
  clearAccessToken,
  getStoredAccessToken,
  storeAccessToken,
} from "../api/apiClient";

import type { AuthUser } from "../types/auth";

interface AuthContextValue {
  user: AuthUser | null;
  isAuthenticated: boolean;
  isInitializing: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

export const AuthContext = createContext<AuthContextValue | undefined>(
  undefined,
);

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isInitializing, setIsInitializing] = useState(true);

  const logout = useCallback(() => {
    clearAccessToken();
    setUser(null);
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      const token = await loginRequest({
        email,
        password,
      });

      storeAccessToken(token.access_token);

      try {
        const authenticatedUser = await getCurrentUserRequest();
        setUser(authenticatedUser);
      } catch (error) {
        logout();
        throw error;
      }
    },
    [logout],
  );

  useEffect(() => {
    async function restoreAuthentication() {
      const existingToken = getStoredAccessToken();

      if (!existingToken) {
        setIsInitializing(false);
        return;
      }

      try {
        const authenticatedUser = await getCurrentUserRequest();
        setUser(authenticatedUser);
      } catch {
        logout();
      } finally {
        setIsInitializing(false);
      }
    }

    void restoreAuthentication();
  }, [logout]);

  useEffect(() => {
    function handleUnauthorized() {
      logout();
    }

    window.addEventListener("opsflow:unauthorized", handleUnauthorized);

    return () => {
      window.removeEventListener("opsflow:unauthorized", handleUnauthorized);
    };
  }, [logout]);

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
