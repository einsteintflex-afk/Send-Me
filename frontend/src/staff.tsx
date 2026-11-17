import { ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { useAuth } from "./auth";
import { DemoBanner, Logo } from "./ui";

export function StaffShell({ title, nav, children, right }: { title: string; nav: { to: string; label: string; end?: boolean; badge?: number }[]; children: ReactNode; right?: ReactNode }) {
  const { user, logout, config } = useAuth();
  return <div className="min-h-full bg-paper">
    <DemoBanner show={config?.demo} />
    <header className="sticky top-0 z-30 bg-navy text-white" style={{ paddingTop: "env(safe-area-inset-top)" }}>
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-4 py-3">
        <div className="flex items-center gap-3"><Logo light /><span className="hidden rounded-full bg-white/10 px-3 py-1 text-xs font-bold sm:inline">{title}</span></div>
        <div className="flex items-center gap-3 text-sm">{right}<span className="hidden text-white/70 sm:inline">{user?.full_name}</span><button onClick={logout} className="rounded-xl bg-white/10 px-3 py-1.5 font-semibold hover:bg-white/20">Sign out</button></div></div>
      <nav className="mx-auto flex max-w-6xl gap-1 overflow-x-auto px-3 pb-2" aria-label={title}>
        {nav.map((n) => <NavLink key={n.to} to={n.to} end={n.end} className={({ isActive }) => `relative whitespace-nowrap rounded-xl px-3.5 py-2 text-sm font-bold ${isActive ? "bg-white text-navy" : "text-white/80 hover:bg-white/10"}`}>
          {n.label}{!!n.badge && <span className="ml-1.5 rounded-full bg-warn px-1.5 text-xs font-extrabold text-navy">{n.badge}</span>}</NavLink>)}</nav></header>
    <main className="mx-auto max-w-6xl p-4 pb-16">{children}</main></div>;
}

export const Stat = ({ label, value, tone = "navy", onClick }: { label: string; value: ReactNode; tone?: "navy" | "teal" | "warn" | "ok" | "bad"; onClick?: () => void }) => {
  const c = { navy: "text-navy", teal: "text-teal-dark", warn: "text-amber-700", ok: "text-ok", bad: "text-bad" }[tone];
  const inner = <><div className="text-xs font-bold uppercase tracking-wide text-muted">{label}</div><div className={`mt-1 text-2xl font-extrabold tabular-nums ${c}`}>{value}</div></>;
  return onClick ? <button onClick={onClick} className="card p-4 text-left transition hover:-translate-y-0.5">{inner}</button> : <div className="card p-4">{inner}</div>;
};

export const SectionTitle = ({ children, right }: { children: ReactNode; right?: ReactNode }) => <div className="mb-3 mt-6 flex items-center justify-between first:mt-0"><h2 className="text-lg font-extrabold text-navy">{children}</h2>{right}</div>;

export function Table({ head, rows, empty = "Nothing to show." }: { head: string[]; rows: ReactNode[][]; empty?: string }) {
  if (!rows.length) return <div className="card p-6 text-center text-sm text-muted">{empty}</div>;
  return <div className="card overflow-x-auto"><table className="w-full min-w-[560px] text-left text-sm"><thead><tr className="border-b border-slate-100 text-xs uppercase tracking-wide text-muted">{head.map((h) => <th key={h} className="px-4 py-3 font-bold">{h}</th>)}</tr></thead>
    <tbody>{rows.map((r, i) => <tr key={i} className="border-b border-slate-50 last:border-0">{r.map((c, j) => <td key={j} className="px-4 py-3 align-middle">{c}</td>)}</tr>)}</tbody></table></div>;
}

export function Toggle({ on, onChange, label }: { on: boolean; onChange: (v: boolean) => void; label: string }) {
  return <button role="switch" aria-checked={on} aria-label={label} onClick={() => onChange(!on)} className={`relative h-7 w-12 flex-none rounded-full transition ${on ? "bg-teal" : "bg-slate-300"}`}>
    <span className={`absolute top-0.5 h-6 w-6 rounded-full bg-white shadow transition-all ${on ? "left-[22px]" : "left-0.5"}`} /></button>;
}
