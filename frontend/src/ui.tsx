import { createContext, ReactNode, useCallback, useContext, useEffect, useRef, useState } from "react";
import { assetUrl } from "./api";

// ---------- toast ----------
const ToastCtx = createContext<(m: string, kind?: "ok" | "err") => void>(() => {});
export const useToast = () => useContext(ToastCtx);
export function ToastProvider({ children }: { children: ReactNode }) {
  const [t, setT] = useState<{ m: string; kind: string } | null>(null);
  const timer = useRef<number>();
  const show = useCallback((m: string, kind: "ok" | "err" = "ok") => { setT({ m, kind }); clearTimeout(timer.current); timer.current = window.setTimeout(() => setT(null), 3200); }, []);
  return <ToastCtx.Provider value={show}>{children}
    {t && <div role="status" className={`fixed left-1/2 z-[2000] -translate-x-1/2 rounded-2xl px-4 py-3 text-sm font-semibold text-white shadow-card ${t.kind === "err" ? "bg-bad" : "bg-navy"}`}
      style={{ bottom: "calc(5.5rem + env(safe-area-inset-bottom))", maxWidth: "92vw" }}>{t.m}</div>}</ToastCtx.Provider>;
}

// ---------- data hook ----------
export function useData<T>(fn: () => Promise<T>, deps: any[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const run = useCallback(() => { setLoading(true); setError(null); return fn().then(setData).catch((e) => setError(e.message)).finally(() => setLoading(false)); }, deps); // eslint-disable-line
  useEffect(() => { run(); }, [run]);
  return { data, error, loading, reload: run, setData };
}

// ---------- atoms ----------
export const Spinner = ({ label = "Loading" }: { label?: string }) => (
  <div className="flex items-center justify-center gap-3 p-10 text-muted" role="status"><span className="h-5 w-5 animate-spin rounded-full border-2 border-teal border-t-transparent" />{label}…</div>);
export const ErrorBox = ({ message, retry }: { message: string; retry?: () => void }) => (
  <div className="m-4 rounded-2xl bg-red-50 p-4 text-sm text-bad"><p className="font-semibold">{message}</p>{retry && <button className="mt-2 font-bold underline" onClick={retry}>Try again</button>}</div>);
export const Empty = ({ title, hint, action }: { title: string; hint?: string; action?: ReactNode }) => (
  <div className="flex flex-col items-center gap-2 p-10 text-center"><div className="grid h-16 w-16 place-items-center rounded-full bg-mint text-3xl text-teal">∅</div>
    <p className="font-bold text-navy">{title}</p>{hint && <p className="max-w-xs text-sm text-muted">{hint}</p>}{action}</div>);
export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return <label className="block"><span className="label">{label}</span>{children}{hint && <span className="mt-1 block text-xs text-muted">{hint}</span>}</label>;
}
export const Badge = ({ children, tone = "mint" }: { children: ReactNode; tone?: "mint" | "warn" | "bad" | "ok" | "navy" | "gray" }) => {
  const c = { mint: "bg-mint text-teal-dark", warn: "bg-amber-100 text-amber-800", bad: "bg-red-100 text-bad", ok: "bg-green-100 text-ok", navy: "bg-navy text-white", gray: "bg-slate-100 text-slate-600" }[tone];
  return <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-bold ${c}`}>{children}</span>;
};
export const StatusBadge = ({ status }: { status: string }) => {
  const tone = ({ Pending: "warn", Accepted: "mint", Shopping: "mint", "On the Way": "navy", Delivered: "ok", Cancelled: "bad" } as any)[status] || "gray";
  return <Badge tone={tone}>{status}</Badge>;
};
export const PayBadge = ({ s }: { s: string }) => <Badge tone={s === "paid" ? "ok" : s === "awaiting_payment" ? "warn" : s.startsWith("refund") ? "warn" : "bad"}>{s.replace(/_/g, " ")}</Badge>;
export function DemoBanner({ show }: { show?: boolean }) {
  return show ? <div className="bg-amber-100 px-4 py-1.5 text-center text-xs font-semibold text-amber-900">DEMO DATA: placeholder rates, map points and accounts</div> : null;
}

// ---------- product picture (honest placeholder when there is no photo) ----------
const TINTS: Record<string, string> = { drinks: "#D7ECFB", snacks: "#FFE6C7", breakfast: "#FFF3B8", noodles: "#FBD9D3", bread: "#F3E2C7", dairy: "#E7F0FF",
  canned: "#E8E0D6", groceries: "#EAF3D8", "personal-care": "#E6DCF8", toiletries: "#DDF1F0", household: "#D9F0E0", stationery: "#FDE7F0", apparel: "#F8DCEC", "frozen-chilled": "#DDEBFA" };
export function ProductImage({ name, category, url, className = "" }: { name: string; category: string; url?: string | null; className?: string }) {
  const src = assetUrl(url);
  if (src) return <img src={src} alt={name} loading="lazy" className={`object-cover ${className}`} />;
  const ini = name.replace(/[^A-Za-z0-9 ]/g, " ").split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]).join("").toUpperCase();
  return <div aria-label={`${name}, no photo yet`} className={`grid place-items-center font-extrabold text-navy/70 ${className}`} style={{ background: TINTS[category] || "#E8F7F4" }}>
    <span className="text-2xl">{ini}</span></div>;
}

// ---------- sheet / modal ----------
export function Sheet({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: string; children: ReactNode }) {
  useEffect(() => { if (!open) return; const k = (e: KeyboardEvent) => e.key === "Escape" && onClose(); window.addEventListener("keydown", k); return () => window.removeEventListener("keydown", k); }, [open, onClose]);
  if (!open) return null;
  return <div className="fixed inset-0 z-[1500] flex items-end justify-center bg-navy/50 sm:items-start sm:pt-12" onClick={onClose}>
    <div role="dialog" aria-modal="true" aria-label={title} className="max-h-[92vh] w-full max-w-lg overflow-y-auto rounded-t-3xl bg-white p-5 sm:rounded-3xl" onClick={(e) => e.stopPropagation()}
      style={{ paddingBottom: "calc(1.25rem + env(safe-area-inset-bottom))" }}>
      <div className="mb-4 flex items-center justify-between"><h2 className="text-lg font-extrabold text-navy">{title}</h2>
        <button className="grid h-9 w-9 place-items-center rounded-full bg-slate-100 text-lg" onClick={onClose} aria-label="Close">×</button></div>
      {children}</div></div>;
}

export function Stepper({ value, onChange, min = 0 }: { value: number; onChange: (n: number) => void; min?: number }) {
  return <div className="inline-flex items-center rounded-2xl border border-slate-200 bg-white">
    <button className="h-10 w-10 text-xl font-bold text-navy disabled:opacity-30" onClick={() => onChange(value - 1)} disabled={value <= min} aria-label="Decrease">−</button>
    <span className="min-w-8 text-center font-bold tabular-nums" aria-live="polite">{value}</span>
    <button className="h-10 w-10 text-xl font-bold text-navy" onClick={() => onChange(value + 1)} aria-label="Increase">+</button></div>;
}

export const Logo = ({ light }: { light?: boolean }) => (
  <span className={`inline-flex items-center gap-2 text-xl font-extrabold tracking-tight ${light ? "text-white" : "text-navy"}`}>
    <svg width="28" height="28" viewBox="0 0 64 64" aria-hidden><rect width="64" height="64" rx="14" fill={light ? "#fff" : "#17324D"} /><path d="M14 40l30-14-8 26-7-10z" fill="#16A6A0" /></svg>Send&nbsp;Me</span>);
