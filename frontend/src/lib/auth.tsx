"use client";

import { useRouter } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { apiGet, login as apiLogin, register as apiRegister, tokenStore } from "./api";
import type { Role, User } from "./types";

interface AuthState {
  user: User | null;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<User>;
  signUp: (input: {
    name: string;
    email: string;
    password: string;
    organization?: string;
  }) => Promise<User>;
  signOut: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;

    if (!tokenStore.access()) {
      // Nothing stored: settle on the next microtask so the server-rendered
      // markup hydrates before the signed-out state is applied.
      void Promise.resolve().then(() => {
        if (active) setLoading(false);
      });
      return () => {
        active = false;
      };
    }

    // Confirm the stored session against the API: a deactivated account or an
    // expired refresh token must not keep a cached user alive.
    apiGet<User>("/auth/me")
      .then((confirmed) => {
        if (!active) return;
        setUser(confirmed);
        setLoading(false);
      })
      .catch(() => {
        if (!active) return;
        tokenStore.clear();
        setUser(null);
        setLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    const pair = await apiLogin(email, password);
    setUser(pair.user);
    return pair.user;
  }, []);

  const signUp = useCallback(
    async (input: { name: string; email: string; password: string; organization?: string }) => {
      const pair = await apiRegister(input);
      setUser(pair.user);
      return pair.user;
    },
    [],
  );

  const signOut = useCallback(() => {
    tokenStore.clear();
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, loading, signIn, signUp, signOut }),
    [user, loading, signIn, signUp, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside <AuthProvider>");
  return context;
}

/** Redirects to /login (or /admin for the wrong role) once auth has settled. */
export function useRequireRole(role?: Role) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    if (!user) {
      router.replace(`/login?next=${encodeURIComponent(window.location.pathname)}`);
      return;
    }
    if (role && user.role !== role) router.replace("/verify");
  }, [user, loading, role, router]);

  return { user, loading: loading || !user || (role ? user.role !== role : false) };
}
