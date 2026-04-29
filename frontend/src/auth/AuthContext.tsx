import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { AuthResponse, AuthUser } from "../api/client";
import { apiFetch } from "../api/client";

const USER_KEY = "travel_user";
const TOKEN_KEY = "travel_token";

interface AuthContextValue {
  user: AuthUser | null;
  token: string | null;
  login: (identifier: string, password: string) => Promise<void>;
  register: (
    username: string,
    email: string,
    password: string
  ) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

function readStoredAuth(): { user: AuthUser | null; token: string | null } {
  const userRaw = localStorage.getItem(USER_KEY);
  const token = localStorage.getItem(TOKEN_KEY);

  if (!userRaw || !token) {
    if (userRaw || token) {
      localStorage.removeItem(USER_KEY);
      localStorage.removeItem(TOKEN_KEY);
    }
    return { user: null, token: null };
  }

  try {
    return { user: JSON.parse(userRaw) as AuthUser, token };
  } catch {
    localStorage.removeItem(USER_KEY);
    localStorage.removeItem(TOKEN_KEY);
    return { user: null, token: null };
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [auth, setAuth] = useState(() => readStoredAuth());

  const persistAuth = useCallback((response: AuthResponse) => {
    localStorage.setItem(USER_KEY, JSON.stringify(response.user));
    localStorage.setItem(TOKEN_KEY, response.access_token);
    setAuth({ user: response.user, token: response.access_token });
  }, []);

  const login = useCallback(
    async (identifier: string, password: string) => {
      const response = await apiFetch<AuthResponse>("/auth/login", {
        method: "POST",
        body: { identifier, password },
      });
      persistAuth(response);
    },
    [persistAuth]
  );

  const register = useCallback(
    async (username: string, email: string, password: string) => {
      const response = await apiFetch<AuthResponse>("/auth/register", {
        method: "POST",
        body: { username, email, password },
      });
      persistAuth(response);
    },
    [persistAuth]
  );

  const logout = useCallback(() => {
    localStorage.removeItem(USER_KEY);
    localStorage.removeItem(TOKEN_KEY);
    setAuth({ user: null, token: null });
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user: auth.user,
      token: auth.token,
      login,
      register,
      logout,
    }),
    [auth.token, auth.user, login, logout, register]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }

  return context;
}
