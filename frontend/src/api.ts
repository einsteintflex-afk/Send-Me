const BASE: string = (import.meta as any).env?.VITE_API_URL ?? "";
const KEY = "sendme.tokens";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) { super(message); this.status = status; }
}

type Tokens = { access_token: string; refresh_token: string };
function read(): Tokens | null { try { return JSON.parse(localStorage.getItem(KEY) || "null"); } catch { return null; } }
function write(t: Tokens | null) { try { t ? localStorage.setItem(KEY, JSON.stringify(t)) : localStorage.removeItem(KEY); } catch { /* storage blocked */ } }
export const tokens = { get: read, set: write };

let onAuthLost: () => void = () => {};
export function setAuthLostHandler(f: () => void) { onAuthLost = f; }

function messageFrom(data: any, status: number): string {
  const d = data?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d) && d.length) {
    const first = d[0];
    const field = Array.isArray(first.loc) ? first.loc[first.loc.length - 1] : "";
    return `${field ? String(field).replace(/_/g, " ") + ": " : ""}${first.msg ?? "Check this field."}`;
  }
  if (status === 429) return "Too many attempts. Wait a minute and try again.";
  if (status >= 500) return "Something went wrong on our side. Please try again.";
  return "Something went wrong.";
}

let refreshing: Promise<boolean> | null = null;
async function refresh(): Promise<boolean> {
  const t = read();
  if (!t) return false;
  refreshing ||= fetch(BASE + "/auth/refresh", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: t.refresh_token }) })
    .then(async (r) => { if (!r.ok) return false; write(await r.json()); return true; })
    .catch(() => false).finally(() => { refreshing = null; });
  return refreshing;
}

export async function api<T = any>(path: string, opts: { method?: string; body?: any; form?: FormData; headers?: Record<string, string> } = {}, retry = true): Promise<T> {
  const t = read();
  const headers: Record<string, string> = { ...(opts.headers || {}) };
  if (t) headers.Authorization = "Bearer " + t.access_token;
  let body: BodyInit | undefined;
  if (opts.form) body = opts.form;
  else if (opts.body !== undefined) { headers["Content-Type"] = "application/json"; body = JSON.stringify(opts.body); }
  let res: Response;
  try { res = await fetch(BASE + path, { method: opts.method || (body ? "POST" : "GET"), headers, body }); }
  catch { throw new ApiError("You look offline. Check your connection and try again.", 0); }
  if (res.status === 401 && retry && t && !path.startsWith("/auth/login")) {
    if (await refresh()) return api<T>(path, opts, false);
    write(null); onAuthLost();
  }
  if (res.status === 204) return undefined as T;
  let data: any = null;
  try { data = await res.json(); } catch { /* empty */ }
  if (!res.ok) throw new ApiError(messageFrom(data, res.status), res.status);
  return data as T;
}

export const assetUrl = (u?: string | null) => (u ? (u.startsWith("http") ? u : BASE + u) : null);
export const money = (n: number | null | undefined) => (n == null ? "—" : "GH₵ " + n.toFixed(2));
export const fmtDate = (s?: string | null) => (s ? new Date(s).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "");
export const fmtTime = (s?: string | null) => (s ? new Date(s).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" }) : "");
/** +233241234567 -> 024 123 4567 (how Ghanaians write numbers). */
export const localPhone = (p?: string | null) => { if (!p) return ""; const m = p.match(/^\+233(\d{2})(\d{3})(\d{4})$/); return m ? `0${m[1]} ${m[2]} ${m[3]}` : p; };
