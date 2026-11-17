import { FormEvent, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, money } from "../api";
import { useAuth } from "../auth";
import { Cart, useCart } from "../cart";
import { Field, Sheet, Spinner, useData, useToast } from "../ui";

const NOTES = ["Call when you arrive", "Deliver to the hostel reception", "Meet me at the main entrance"];

export function AddDestination({ open, onClose, onSaved }: { open: boolean; onClose: () => void; onSaved: (a: any) => void }) {
  const { user } = useAuth(); const toast = useToast();
  const [kind, setKind] = useState("hostel"); const [hostels, setHostels] = useState<any[]>([]);
  const [f, setF] = useState({ label: "", hostel: "", block: "", room: "", place: "" }); const [pos, setPos] = useState<{ lat: number; lng: number } | null>(null); const [busy, setBusy] = useState(false);
  useEffect(() => { if (!open) return; api<any[]>("/universities").then((u) => { const c = u.find((x) => x.id === user?.university_id)?.campuses?.[0] || u[0]?.campuses?.[0]; if (c) api(`/campuses/${c.id}/hostels`).then(setHostels); }); }, [open, user]);
  const locate = () => navigator.geolocation?.getCurrentPosition((p) => { setPos({ lat: p.coords.latitude, lng: p.coords.longitude }); toast("Location captured"); }, () => toast("Couldn't get your location. Allow location access and try again.", "err"), { enableHighAccuracy: true, timeout: 10000 });
  const submit = async (e: FormEvent) => { e.preventDefault(); setBusy(true);
    try { const a = await api("/auth/addresses", { body: { kind, label: f.label || (kind === "hostel" ? f.hostel : f.place), hostel: f.hostel || null, block: f.block || null, room: f.room || null, place: f.place || null, latitude: pos?.lat ?? null, longitude: pos?.lng ?? null } });
      onSaved(a); onClose(); } catch (x: any) { toast(x.message, "err"); } finally { setBusy(false); } };
  return <Sheet open={open} onClose={onClose} title="Add delivery destination">
    <div className="mb-4 grid grid-cols-3 gap-2 rounded-2xl bg-slate-100 p-1 text-sm font-bold">{[["hostel", "Hostel & room"], ["pickup_point", "Pickup point"], ["other", "Other spot"]].map(([k, l]) =>
      <button key={k} type="button" onClick={() => setKind(k)} className={`rounded-xl py-2 ${kind === k ? "bg-white text-navy shadow-card" : "text-muted"}`}>{l}</button>)}</div>
    <form onSubmit={submit} className="space-y-3">
      {kind === "hostel" ? <>
        <Field label="Hostel">{hostels.length ? <select className="input" value={f.hostel} onChange={(e) => setF({ ...f, hostel: e.target.value })} required><option value="">Choose hostel</option>{hostels.map((h) => <option key={h.id}>{h.name}</option>)}</select> : <input className="input" value={f.hostel} onChange={(e) => setF({ ...f, hostel: e.target.value })} required />}</Field>
        <div className="grid grid-cols-2 gap-3"><Field label="Block"><input className="input" value={f.block} onChange={(e) => setF({ ...f, block: e.target.value })} /></Field><Field label="Room number"><input className="input" value={f.room} onChange={(e) => setF({ ...f, room: e.target.value })} required /></Field></div></> :
        <Field label={kind === "pickup_point" ? "Campus pickup point" : "Campus location"}><input className="input" value={f.place} onChange={(e) => setF({ ...f, place: e.target.value })} placeholder="e.g. Main gate, library steps" required /></Field>}
      <Field label="Nickname (optional)"><input className="input" value={f.label} onChange={(e) => setF({ ...f, label: e.target.value })} placeholder="e.g. My room" /></Field>
      {kind !== "hostel" && <button type="button" className="btn btn-soft w-full" onClick={locate}>📍 {pos ? "Location captured ✓" : "Use my current location (improves delivery price)"}</button>}
      <button className="btn btn-primary w-full" disabled={busy}>Save destination</button></form></Sheet>;
}

export default function Checkout() {
  const nav = useNavigate(); const toast = useToast(); const { config } = useAuth(); const { cart, refresh, setCart } = useCart();
  const addrs = useData(() => api<any[]>("/auth/addresses"), []);
  const [sel, setSel] = useState<number | null>(null); const [note, setNote] = useState(""); const [adding, setAdding] = useState(false);
  const [busy, setBusy] = useState(false); const [err, setErr] = useState(""); const [quote, setQuote] = useState<Cart | null>(null);
  const idem = useRef(crypto.randomUUID?.() || String(Date.now()));
  useEffect(() => { if (addrs.data && sel == null) setSel((addrs.data.find((a) => a.is_default) || addrs.data[0])?.id ?? null); }, [addrs.data, sel]);
  useEffect(() => { if (sel) api<Cart>(`/cart?address_id=${sel}`).then(setQuote).catch(() => {}); }, [sel, cart?.items.length]);
  const c = quote || cart;
  if (!cart || addrs.loading) return <Spinner />;
  if (cart.items.length + cart.requests.length === 0) return <div className="p-8 text-center"><p className="mb-3 text-muted">Your cart is empty.</p><Link className="btn btn-primary" to="/explore">Browse shop</Link></div>;
  const pay = async () => {
    setErr(""); if (!sel) { setErr("Choose where to deliver."); return; } setBusy(true);
    try {
      const o = await api("/checkout", { body: { address_id: sel, instructions: note || null }, headers: { "Idempotency-Key": idem.current } });
      await refresh();
      const p = await api("/orders/" + o.id + "/pay", { body: {} });
      window.location.href = p.authorization_url;
    } catch (x: any) { setErr(x.message); setBusy(false); }
  };
  const feeText = c?.delivery_fee != null ? money(c.delivery_fee) : "Choose a destination";
  return <div className="space-y-5 p-4 pb-8">
    <div className="flex items-center gap-2"><button onClick={() => nav(-1)} className="grid h-10 w-10 place-items-center rounded-full bg-white text-xl shadow-card" aria-label="Back">‹</button><h1 className="text-xl font-extrabold text-navy">Checkout</h1></div>
    <section><h2 className="mb-2 font-extrabold text-navy">Deliver to</h2><div className="space-y-2">
      {addrs.data?.map((a) => <label key={a.id} className={`flex cursor-pointer items-start gap-3 rounded-2xl border-2 p-3 ${sel === a.id ? "border-teal bg-mint" : "border-slate-200 bg-white"}`}>
        <input type="radio" name="addr" checked={sel === a.id} onChange={() => setSel(a.id)} className="mt-1 h-4 w-4 accent-teal" />
        <span className="text-sm"><b className="text-navy">{a.label}</b><br /><span className="text-muted">{a.kind === "hostel" ? [a.hostel, a.block && `Block ${a.block}`, `Room ${a.room}`].filter(Boolean).join(", ") : a.place}</span></span></label>)}
      <button className="btn btn-ghost w-full" onClick={() => setAdding(true)}>＋ Add hostel, pickup point or other spot</button></div></section>
    <section><h2 className="mb-2 font-extrabold text-navy">Delivery instructions</h2>
      <div className="mb-2 flex flex-wrap gap-2">{NOTES.map((n) => <button key={n} className={`chip ${note === n ? "chip-on" : ""}`} onClick={() => setNote(note === n ? "" : n)}>{n}</button>)}</div>
      <input className="input" value={note} onChange={(e) => setNote(e.target.value.slice(0, 300))} placeholder="Anything the rider should know" aria-label="Delivery instructions" /></section>
    <section className="card space-y-2 p-4"><h2 className="font-extrabold text-navy">Order summary</h2>
      {c?.items.map((i) => <div key={i.id} className="flex justify-between text-sm"><span>{i.quantity} × {i.name}{i.variant ? ` (${i.variant})` : ""}</span><span className="tabular-nums">{money(i.line_total)}</span></div>)}
      {c?.requests.map((r) => <div key={r.id} className="flex justify-between rounded-xl bg-amber-50 px-2 py-1 text-sm"><span>Request: {r.quantity} × {r.name}</span><span className="font-semibold text-amber-800">{r.status === "priced" ? money((r.unit_price || 0) * r.quantity) : "Price to be confirmed"}</span></div>)}
      <div className="flex justify-between border-t border-slate-100 pt-2 text-sm"><span className="text-muted">Subtotal</span><span className="tabular-nums">{money(c?.subtotal)}</span></div>
      <div className="flex justify-between text-sm"><span className="text-muted">Delivery fee{c?.delivery_distance_km != null && ` (${c.delivery_distance_km.toFixed(2)} km${c.delivery_method === "straight_line" ? ", approx." : ""})`}</span><span className="tabular-nums">{feeText}</span></div>
      <div className="flex justify-between border-t border-dashed border-slate-300 pt-2 text-lg font-extrabold text-navy"><span>Total to pay now</span><span className="tabular-nums">{money(c?.total)}</span></div>
      {c?.pending_confirmation && <p className="text-xs text-amber-800">Requested items aren't charged yet. The shop will quote them and you approve before paying.</p>}</section>
    <section className="card p-4 text-sm"><h2 className="mb-1 font-extrabold text-navy">Payment</h2>
      <p className="text-navy">Mobile Money (MTN, Telecel, AT) or bank card, securely through Paystack.</p>
      {config?.payment_mode === "mock" && <p className="mt-2 rounded-xl bg-amber-50 p-2 font-semibold text-amber-900">TEST MODE: payment is simulated. No real money moves.</p>}
      {config?.payment_mode === "test" && <p className="mt-2 rounded-xl bg-amber-50 p-2 font-semibold text-amber-900">Paystack test mode: use test cards only.</p>}</section>
    {err && <p role="alert" className="rounded-xl bg-red-50 p-3 text-sm font-semibold text-bad">{err}</p>}
    <button className="btn btn-primary w-full text-lg" disabled={busy || !sel || c?.total == null} onClick={pay}>{busy ? "Preparing payment…" : `Pay ${money(c?.total)}`}</button>
    <AddDestination open={adding} onClose={() => setAdding(false)} onSaved={(a) => { addrs.reload(); setSel(a.id); }} />
  </div>;
}
