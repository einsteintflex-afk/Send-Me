import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import { api, fmtDate } from "../api";
import { useAuth } from "../auth";
import { Empty, Field, Spinner, useData, useToast } from "../ui";
import { AddDestination } from "./Checkout";

export function Account() {
  const { user, logout, reload } = useAuth(); const toast = useToast();
  const addrs = useData(() => api<any[]>("/auth/addresses"), []);
  const [adding, setAdding] = useState(false); const [name, setName] = useState(user?.full_name || ""); const [phone, setPhone] = useState(user?.phone || ""); const [msg, setMsg] = useState("");
  const save = async (e: FormEvent) => { e.preventDefault(); try { await api("/auth/me", { method: "PATCH", body: { full_name: name, phone } }); await reload(); toast("Profile saved"); } catch (x: any) { toast(x.message, "err"); } };
  const pref = async (k: string, v: boolean) => { try { await api("/auth/me", { method: "PATCH", body: { notification_prefs: { ...(user?.notification_prefs || {}), [k]: v } } }); await reload(); } catch (x: any) { toast(x.message, "err"); } };
  const del = async (id: number) => { try { await api(`/auth/addresses/${id}`, { method: "DELETE" }); addrs.reload(); } catch (x: any) { toast(x.message, "err"); } };
  const makeDefault = async (a: any) => { try { await api(`/auth/addresses/${a.id}`, { method: "PUT", body: { ...a, is_default: true } }); addrs.reload(); } catch (x: any) { toast(x.message, "err"); } };
  const complain = async (e: FormEvent) => { e.preventDefault(); try { await api("/support/complaints", { body: { message: msg } }); setMsg(""); toast("Sent. We'll look into it."); } catch (x: any) { toast(x.message, "err"); } };
  return <div className="space-y-5 p-4 pb-8">
    <h1 className="text-2xl font-extrabold text-navy">Account</h1>
    {!user?.email_verified && <div className="rounded-2xl bg-amber-50 p-3 text-sm text-amber-900">Your email isn't verified yet. <button className="font-bold underline" onClick={() => api("/auth/resend-verification", { body: {} }).then(() => toast("Verification link sent"))}>Send link</button></div>}
    <form onSubmit={save} className="card space-y-3 p-4"><h2 className="font-extrabold text-navy">Profile</h2>
      <Field label="Full name"><input className="input" value={name} onChange={(e) => setName(e.target.value)} /></Field>
      <Field label="Phone"><input className="input" value={phone} onChange={(e) => setPhone(e.target.value)} inputMode="tel" /></Field>
      <div className="text-sm text-muted">{user?.email}</div><button className="btn btn-primary w-full">Save profile</button></form>
    <section className="card space-y-3 p-4"><h2 className="font-extrabold text-navy">Delivery destinations</h2>
      {addrs.loading ? <Spinner /> : addrs.data?.map((a) => <div key={a.id} className="flex items-start justify-between gap-2 rounded-2xl bg-slate-50 p-3 text-sm">
        <div><b className="text-navy">{a.label}</b> {a.is_default && <span className="rounded-full bg-mint px-2 text-xs font-bold text-teal-dark">Default</span>}<div className="text-muted">{a.kind === "hostel" ? [a.hostel, a.block && `Block ${a.block}`, `Room ${a.room}`].filter(Boolean).join(", ") : a.place}</div></div>
        <div className="flex flex-col items-end gap-1 text-xs font-bold">{!a.is_default && <button className="text-teal-dark" onClick={() => makeDefault(a)}>Make default</button>}<button className="text-bad" onClick={() => del(a.id)}>Delete</button></div></div>)}
      <button className="btn btn-soft w-full" onClick={() => setAdding(true)}>＋ Add destination</button></section>
    <section className="card space-y-3 p-4"><h2 className="font-extrabold text-navy">Notifications</h2>
      {[["in_app", "In-app notifications"], ["push", "Push notifications (coming soon)"]].map(([k, l]) => <label key={k} className="flex items-center justify-between text-sm"><span>{l}</span>
        <input type="checkbox" className="h-5 w-5 accent-teal" checked={!!(user?.notification_prefs as any)?.[k]} disabled={k === "push"} onChange={(e) => pref(k, e.target.checked)} /></label>)}
      <Link to="/notifications" className="btn btn-ghost w-full">View notifications</Link></section>
    <form onSubmit={complain} className="card space-y-3 p-4"><h2 className="font-extrabold text-navy">Need help?</h2>
      <textarea className="input" rows={3} value={msg} onChange={(e) => setMsg(e.target.value)} placeholder="Tell us what went wrong" required minLength={5} /><button className="btn btn-ghost w-full">Send to Send Me support</button></form>
    <button className="btn btn-danger w-full" onClick={logout}>Sign out</button>
    <AddDestination open={adding} onClose={() => setAdding(false)} onSaved={() => addrs.reload()} /></div>;
}

export function Notifications() {
  const { data, loading, reload } = useData(() => api<any[]>("/notifications"), []);
  return <div className="space-y-3 p-4">
    <div className="flex items-center justify-between"><h1 className="text-2xl font-extrabold text-navy">Notifications</h1>
      <button className="text-sm font-bold text-teal-dark" onClick={() => api("/notifications/read", { body: {} }).then(reload)}>Mark all read</button></div>
    {loading ? <Spinner /> : !data?.length ? <Empty title="Nothing yet" hint="Order and price updates will appear here." /> : data.map((n) =>
      <Link key={n.id} to={n.order_id ? `/orders/${n.order_id}` : "#"} className={`card block p-4 ${n.read ? "" : "border-l-4 border-teal"}`}>
        <div className="flex justify-between gap-2"><b className="text-navy">{n.title}</b><span className="text-xs text-muted">{fmtDate(n.created_at)}</span></div><p className="text-sm text-navy/80">{n.body}</p></Link>)}</div>;
}
