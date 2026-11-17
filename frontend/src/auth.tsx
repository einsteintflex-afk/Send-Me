import { createContext, ReactNode, useCallback, useContext, useEffect, useState } from "react";
import { api, setAuthLostHandler, tokens } from "./api";

export type User = { id: number; full_name: string; email: string | null; phone: string; role: string; email_verified: boolean;
  university_id?: number; notification_prefs?: { in_app: boolean; push: boolean } };
type Ctx = { user: User | null; loading: boolean; login: (id: string, pw: string) => Promise<User>; register: (b: any) => Promise<User>;
  logout: () => void; reload: () => Promise<void>; config: Config | null };
export type Config = { currency: string; payment_mode: string; maps_mode: string; demo: boolean; tagline: string };

const AuthCtx = createContext<Ctx>(null as any);
export const useAuth = () => useContext(AuthCtx);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [config, setConfig] = useState<Config | null>(null);

  const reload = useCallback(async () => {
    if (!tokens.get()) { setUser(null); return; }
    try { setUser(await api<User>("/auth/me")); } catch { setUser(null); }
  }, []);
  useEffect(() => {
    setAuthLostHandler(() => setUser(null));
    api<Config>("/config").then(setConfig).catch(() => {});
    reload().finally(() => setLoading(false));
  }, [reload]);

  const login = async (identifier: string, password: string) => {
    const r = await api("/auth/login", { body: { identifier, password } });
    tokens.set({ access_token: r.access_token, refresh_token: r.refresh_token });
    setUser(r.user); return r.user as User;
  };
  const register = async (b: any) => {
    const r = await api("/auth/register", { body: b });
    tokens.set({ access_token: r.access_token, refresh_token: r.refresh_token });
    setUser(r.user); return r.user as User;
  };
  const logout = () => { tokens.set(null); setUser(null); };
  return <AuthCtx.Provider value={{ user, loading, login, register, logout, reload, config }}>{children}</AuthCtx.Provider>;
}

export const homeFor = (role?: string) => ({ student: "/", shop_admin: "/shop", shop_staff: "/shop", rider: "/rider", super_admin: "/admin" } as Record<string, string>)[role || ""] || "/welcome";
