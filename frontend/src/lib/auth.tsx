"use client";

import { useQueryClient } from "@tanstack/react-query";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { apiFetch, refreshSession, setAccessToken } from "@/lib/api";
import type { LoginBody, SignupBody, TokenResponse, User } from "@/types/api";

type Status = "loading" | "authenticated" | "anonymous";

interface AuthContextValue {
  status: Status;
  user: User | null;
  setUser: (u: User) => void;
  login: (body: LoginBody) => Promise<User>;
  signup: (body: SignupBody) => Promise<User>;
  logout: () => Promise<void>;
  forget: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<Status>("loading");
  const [user, setUserState] = useState<User | null>(null);
  const queryClient = useQueryClient();

  const accept = useCallback((data: TokenResponse): User => {
    setAccessToken(data.access_token);
    setUserState(data.user);
    setStatus("authenticated");
    return data.user;
  }, []);

  const forget = useCallback(() => {
    setAccessToken(null);
    setUserState(null);
    setStatus("anonymous");
    queryClient.clear();
  }, [queryClient]);

  useEffect(() => {
    let alive = true;
    refreshSession().then((data) => {
      if (!alive) return;
      if (data) accept(data);
      else setStatus("anonymous");
    });
    return () => {
      alive = false;
    };
  }, [accept]);

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      user,
      setUser: setUserState,
      login: async (body) =>
        accept(await apiFetch<TokenResponse>("/auth/login", { method: "POST", body, auth: false })),
      signup: async (body) =>
        accept(await apiFetch<TokenResponse>("/auth/signup", { method: "POST", body, auth: false })),
      logout: async () => {
        try {
          await apiFetch("/auth/logout", { method: "POST", auth: false });
        } finally {
          forget();
        }
      },
      forget,
    }),
    [status, user, accept, forget],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
