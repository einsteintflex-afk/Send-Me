import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api, fmtDate, fmtTime, localPhone, money } from "../api";
import { useCart } from "../cart";
import MapView, { Pin } from "../MapView";
import { Empty, ErrorBox, PayBadge, Spinner, StatusBadge, useData, useToast } from "../ui";

const STEPS = [
  { s: "Pending", d: "Order submitted and awaiting shop acceptance." },
  { s: "Accepted", d: "The shop has accepted your order." },
  { s: "Shopping", d: "The shop is preparing your order." },
  { s: "On the Way", d: "Your order is with the rider." },
  { s: "Delivered", d: "You've received your order." },
];

export function OrdersList() {
  const { data, loading, error, reload } = useData(() => api<any[]>("/orders"), []);
  const [tab, setTab] = useState<"active" | "past">("active");
  if (loading) return <Spinner />; if (error) return <ErrorBox message={error} retry={reload} />;
  const open = (o: any) => !["Delivered", "Cancelled"].includes(o.status);
  const list = (data || []).filter((o) => (tab === "active" ? open(o) : !open(o)));
  return <div className="space-y-4 p-4">
    <h1 className="text-2xl font-extrabold text-navy">Your orders</h1>
    <div className="grid grid-cols-2 rounded-2xl bg-slate-100 p-1 text-sm font-bold">{(["active", "past"] as const).map((t) => <button key={t} onClick={() => setTab(t)} className={`rounded-xl py-2 capitalize ${tab === t ? "bg-white text-navy shadow-card" : "text-muted"}`}>{t === "active" ? "Current" : "Past"}</button>)}</div>
    {list.length === 0 ? <Empty title={tab === "active" ? "No current orders" : "No past orders yet"} hint="Your orders will show up here." action={<Link to="/explore" className="btn btn-primary mt-2">Start shopping</Link>} /> :
      list.map((o) => <Link key={o.id} to={`/orders/${o.id}`} className="card block space-y-2 p-4">
        <div className="flex items-center justify-between"><b className="text-navy">{o.number || `Order #${o.id}`}</b><StatusBadge status={o.status} /></div>
        <p className="line-clamp-2 text-sm text-muted">{o.items.map((i: any) => `${i.quantity}× ${i.name}`).join(", ")}</p>
        <div className="flex items-center justify-between text-sm"><span className="text-muted">{fmtDate(o.created_at)}</span><span className="flex items-center gap-2"><PayBadge s={o.payment_status} /><b className="tabular-nums text-navy">{money(o.total)}</b></span></div></Link>)}
  </div>;
}

function Tracker({ orderId, active }: { orderId: number; active: boolean }) {
  const [t, setT] = useState<any>(null);
  useEffect(() => { let on = true; const pull = () => api(`/orders/${orderId}/tracking`).then((x) => on && setT(x)).catch(() => {}); pull();
    const h = active ? window.setInterval(pull, 8000) : undefined; return () => { on = false; clearInterval(h); }; }, [orderId, active]);
  const pins = useMemo<Pin[]>(() => { if (!t) return []; const p: Pin[] = [];
    if (t.shop) p.push({ lat: t.shop.latitude, lng: t.shop.longitude, label: t.shop.name, color: "#17324D", glyph: "S" });
    if (t.rider_position) p.push({ lat: t.rider_position.latitude, lng: t.rider_position.longitude, label: "Your rider", color: "#16A6A0", glyph: "R", pulse: true });
    if (t.destination) p.push({ lat: t.destination.latitude, lng: t.destination.longitude, label: "You", color: "#F0A43A", glyph: "★" }); return p; }, [t]);
  if (!t) return null;
  return <section className="card space-y-3 p-4"><h2 className="font-extrabold text-navy">Live tracking</h2>
    {!t.live && <p className="rounded-xl bg-mint p-3 text-sm text-navy">{t.status === "Delivered" || t.status === "Cancelled" ? "Tracking has ended." : "Live tracking starts when your rider picks up the order."}</p>}
    {pins.length > 0 ? <MapView pins={pins} /> : <p className="rounded-xl bg-slate-50 p-3 text-sm text-muted">The map isn't available yet because delivery locations haven't been set.</p>}
    {t.live && (t.rider_position ? <div className="flex items-center justify-between text-sm">
      <span className={t.rider_position.stale ? "font-semibold text-amber-700" : "font-semibold text-ok"}>{t.rider_position.stale ? "Rider location is out of date" : "● Live"} · updated {fmtTime(t.rider_position.updated_at)}</span>
      {t.distance_to_destination_km != null && <b className="text-navy">{t.distance_to_destination_km < 1 ? `${Math.round(t.distance_to_destination_km * 1000)} m away` : `${t.distance_to_destination_km} km away`}</b>}</div>
      : <p className="text-sm text-muted">Waiting for your rider's location…</p>)}</section>;
}

export function OrderDetail() {
  const { id } = useParams(); const [sp] = useSearchParams(); const toast = useToast(); const nav = useNavigate(); const { refresh } = useCart();
  const { data: o, loading, error, reload } = useData(() => api<any>(`/orders/${id}`), [id]);
  const [stars, setStars] = useState(0); const [busy, setBusy] = useState(false);
  useEffect(() => { const ref = sp.get("verify"); if (ref) api(`/payments/verify/${ref}`, { body: {} }).then(() => reload()).catch(() => {}); }, [sp]); // eslint-disable-line
  useEffect(() => { if (!o || ["Delivered", "Cancelled"].includes(o.status)) return; const h = window.setInterval(reload, 10000); return () => clearInterval(h); }, [o?.status]); // eslint-disable-line
  if (loading && !o) return <Spinner />; if (error || !o) return <ErrorBox message={error || "Order not found"} retry={reload} />;
  const idx = STEPS.findIndex((s) => s.s === o.status); const cancelled = o.status === "Cancelled";
  const act = async (fn: () => Promise<any>, ok: string) => { setBusy(true); try { await fn(); toast(ok); await reload(); await refresh(); } catch (e: any) { toast(e.message, "err"); } finally { setBusy(false); } };
  const payNow = async () => { setBusy(true); try { const p = await api(`/orders/${o.id}/pay`, { body: {} }); window.location.href = p.authorization_url; } catch (e: any) { toast(e.message, "err"); setBusy(false); } };
  const d = o.destination;
  return <div className="space-y-4 p-4 pb-8">
    <div className="flex items-center gap-2"><button onClick={() => nav("/orders")} className="grid h-10 w-10 place-items-center rounded-full bg-white text-xl shadow-card" aria-label="Back">‹</button>
      <div className="flex-1"><h1 className="text-xl font-extrabold text-navy">{o.number || `Order #${o.id}`}</h1><div className="text-xs text-muted">{fmtDate(o.created_at)}</div></div><StatusBadge status={o.status} /></div>
    {o.payment_status === "paid" && o.status === "Pending" && <div className="rounded-2xl bg-green-50 p-4 text-ok"><b>Payment received. Order confirmed!</b><div className="text-sm">We've sent it to {o.shop.name}.</div></div>}
    {o.payment_status === "awaiting_payment" && !cancelled && <div className="rounded-2xl bg-amber-50 p-4"><b className="text-amber-900">Payment not completed</b><p className="text-sm text-amber-900">The shop only receives your order after payment is confirmed.</p><button className="btn btn-primary mt-3 w-full" disabled={busy} onClick={payNow}>Pay {money(o.total)}</button></div>}
    {(o.payment_status === "failed" || o.payment_status === "abandoned") && !cancelled && <div className="rounded-2xl bg-red-50 p-4"><b className="text-bad">Payment didn't go through</b><button className="btn btn-primary mt-3 w-full" disabled={busy} onClick={payNow}>Try paying again</button></div>}
    {o.payment_status === "refund_pending" && <div className="rounded-2xl bg-amber-50 p-4 text-sm text-amber-900"><b>Refund pending.</b> Your payment will be refunded for this cancelled order.</div>}
    {o.payment_status === "paid" && !cancelled && o.estimated_arrival && o.status !== "Delivered" && <div className="flex items-center gap-3 rounded-2xl bg-mint p-4"><span className="text-2xl">⏱</span><div><div className="text-sm text-muted">Estimated arrival</div><b className="text-lg text-navy">{fmtTime(o.estimated_arrival)}</b> <span className="text-xs text-muted">(estimate)</span></div></div>}
    <section className="card p-4"><h2 className="mb-3 font-extrabold text-navy">Order progress</h2>
      {cancelled ? <div className="flex gap-3"><span className="grid h-7 w-7 place-items-center rounded-full bg-bad font-bold text-white">×</span><div><b className="text-bad">Cancelled</b><p className="text-sm text-muted">{o.cancel_reason || "This order was cancelled."}</p></div></div> :
        <ol>{STEPS.map((s, i) => { const done = i < idx, now = i === idx; return <li key={s.s} className="relative flex gap-3 pb-5 last:pb-0">
          {i < STEPS.length - 1 && <span className={`absolute left-[13px] top-7 h-full w-0.5 ${done ? "bg-teal" : "bg-slate-200"}`} />}
          <span className={`z-10 grid h-7 w-7 flex-none place-items-center rounded-full text-xs font-extrabold ${done ? "bg-teal text-white" : now ? "bg-warn text-navy ring-4 ring-warn/30" : "border-2 border-slate-200 bg-white text-muted"}`}>{done ? "✓" : i + 1}</span>
          <div><b className={now ? "text-teal-dark" : done ? "text-navy" : "text-muted"}>{s.s}</b>{(now || done) && <p className="text-sm text-muted">{s.d}</p>}</div></li>; })}</ol>}</section>
    {!cancelled && o.payment_status === "paid" && <Tracker orderId={o.id} active={o.status === "On the Way"} />}
    <section className="card space-y-2 p-4"><h2 className="font-extrabold text-navy">Delivery</h2>
      <p className="text-sm"><span className="text-muted">To:</span> <b className="text-navy">{d.kind === "hostel" ? [d.hostel, d.block && `Block ${d.block}`, d.room && `Room ${d.room}`].filter(Boolean).join(", ") : d.place}</b></p>
      {o.instructions && <p className="text-sm"><span className="text-muted">Instructions:</span> {o.instructions}</p>}
      <div className="rounded-2xl bg-slate-50 p-3 text-sm"><div className="font-bold text-navy">Rider</div>
        {o.rider ? <div>{o.rider.name} · <a className="font-semibold text-teal-dark" href={`tel:${o.rider.phone}`}>{localPhone(o.rider.phone)}</a></div> : <div className="text-muted">Not assigned yet. Details appear here once a rider is assigned.</div>}</div>
      <div className="rounded-2xl bg-slate-50 p-3 text-sm"><div className="font-bold text-navy">{o.shop.name}</div><div className="text-muted">{o.shop.location}</div>{o.shop.phones.map((p: string) => <a key={p} className="mr-3 font-semibold text-teal-dark" href={`tel:${p}`}>{localPhone(p)}</a>)}</div></section>
    <section className="card space-y-2 p-4"><h2 className="font-extrabold text-navy">Items</h2>
      {o.items.map((i: any) => <div key={i.id} className={`flex justify-between gap-2 text-sm ${i.is_request ? "rounded-xl bg-amber-50 p-2" : ""}`}><span>{i.quantity} × {i.name}{i.variant && ` (${i.variant})`}{i.is_request && <em className="text-amber-800"> · requested</em>}</span>
        <span className="font-semibold tabular-nums">{i.line_total != null ? money(i.line_total) : "To be confirmed"}</span></div>)}
      <div className="flex justify-between border-t border-slate-100 pt-2 text-sm"><span className="text-muted">Subtotal</span><span className="tabular-nums">{money(o.subtotal)}</span></div>
      <div className="flex justify-between text-sm"><span className="text-muted">Delivery fee</span><span className="tabular-nums">{money(o.delivery_fee)}</span></div>
      <div className="flex justify-between text-lg font-extrabold text-navy"><span>Total</span><span className="tabular-nums">{money(o.total)}</span></div></section>
    <RequestApprovals o={o} busy={busy} act={act} />
    {o.status === "Pending" && <button className="btn btn-danger w-full" disabled={busy} onClick={() => act(() => api(`/orders/${o.id}/cancel`, { body: {} }), "Order cancelled")}>Cancel order</button>}
    {o.status === "Delivered" && <div className="card space-y-2 p-4 text-center"><b className="text-navy">How was your delivery?</b><div className="flex justify-center gap-1">{[1, 2, 3, 4, 5].map((n) => <button key={n} className={`text-3xl ${n <= stars ? "text-warn" : "text-slate-300"}`} onClick={() => setStars(n)} aria-label={`${n} star`}>★</button>)}</div>
      {stars > 0 && <button className="btn btn-primary w-full" onClick={() => act(() => api(`/orders/${o.id}/review`, { body: { rating: stars } }), "Thanks for your feedback!")}>Submit rating</button>}</div>}
  </div>;
}

function RequestApprovals({ o, busy, act }: any) {
  return <>{o.items.filter((i: any) => i.is_request).map((i: any) => <PriceApproval key={i.id} orderId={o.id} item={i} act={act} busy={busy} />)}</>;
}
function PriceApproval({ orderId, item, act, busy }: any) {
  const { data } = useData(() => api<any[]>("/notifications"), [item.id]);
  if (item.unit_price != null) return null;
  const n = data?.find((x: any) => x.kind === "request_priced" && x.order_id === orderId && x.body.includes(item.name));
  if (!n) return <div className="rounded-2xl bg-amber-50 p-4 text-sm text-amber-900"><b>{item.name}</b>: waiting for the shop to send a price.</div>;
  return <div className="rounded-2xl border-2 border-warn bg-amber-50 p-4"><b className="text-navy">{n.title}</b><p className="text-sm text-navy">{n.body}</p>
    <div className="mt-3 flex gap-2"><button className="btn btn-primary flex-1" disabled={busy} onClick={() => act(async () => { const p = await api(`/orders/${orderId}/requests/${item.request_id}/approve`, { body: {} }); window.location.href = p.authorization_url; }, "Opening payment…")}>Approve &amp; pay</button>
      <button className="btn btn-ghost flex-1" disabled={busy} onClick={() => act(() => api(`/orders/${orderId}/requests/${item.request_id}/decline`, { body: {} }), "Price declined")}>Decline</button></div></div>;
}

export function MockPay() {
  const [sp] = useSearchParams(); const nav = useNavigate(); const ref = sp.get("reference") || "";
  const { data, loading, error } = useData(() => api<any>(`/payments/verify/${ref}`, { body: {} }), [ref]);
  const [busy, setBusy] = useState(false);
  const finish = async (outcome: string) => { setBusy(true); try { await api(`/dev/mock-pay/${ref}`, { body: { outcome } }); const r = await api(`/payments/verify/${ref}`, { body: {} }); nav(`/orders/${r.order.id}`, { replace: true }); } catch { setBusy(false); } };
  if (loading) return <Spinner />; if (error || !data) return <ErrorBox message={error || "Payment not found"} />;
  return <div className="space-y-4 p-5">
    <div className="rounded-3xl bg-amber-100 p-5 text-amber-950"><div className="text-xs font-extrabold uppercase tracking-wide">Test mode · simulated payment</div>
      <p className="mt-1 text-sm">This stands in for Paystack. No real money moves. Real Paystack checkout appears once a Paystack key is configured.</p></div>
    <div className="card space-y-1 p-5 text-center"><div className="text-sm text-muted">Pay Send Me</div><div className="text-4xl font-extrabold tabular-nums text-navy">{money(data.order.total)}</div><div className="text-sm text-muted">Order #{data.order.id}</div></div>
    <button className="btn btn-primary w-full" disabled={busy} onClick={() => finish("success")}>Simulate successful payment</button>
    <button className="btn btn-ghost w-full" disabled={busy} onClick={() => finish("failed")}>Simulate failed payment</button>
    <button className="btn btn-ghost w-full" disabled={busy} onClick={() => finish("abandoned")}>Cancel</button></div>;
}
