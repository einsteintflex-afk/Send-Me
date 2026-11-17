import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, Navigate, Route, Routes, useNavigate, useParams } from "react-router-dom";
import { api, fmtDate, localPhone, money } from "../api";
import { useAuth } from "../auth";
import MapView, { Pin } from "../MapView";
import { Badge, DemoBanner, Empty, ErrorBox, Field, Logo, Sheet, Spinner, StatusBadge, useData, useToast } from "../ui";

const dest = (d: any) => (d.kind === "hostel" ? [d.hostel, d.block && `Block ${d.block}`, d.room && `Room ${d.room}`].filter(Boolean).join(", ") : d.place);
const navUrl = (o: any, t: any) => { const d = t?.destination;
  return d ? `https://www.google.com/maps/dir/?api=1&destination=${d.latitude},${d.longitude}&travelmode=walking`
    : `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent((o.destination.hostel || o.destination.place || "") + ", Ghana")}&travelmode=walking`; };

/** Shares the rider's GPS while they have an order On the Way (or when they switch it on). */
function useLocationSharing(active: boolean) {
  const [state, setState] = useState<"off" | "asking" | "live" | "denied" | "unsupported">("off"); const last = useRef(0); const watch = useRef<number | null>(null);
  const push = useCallback((lat: number, lng: number) => { const now = Date.now(); if (now - last.current < 8000) return; last.current = now; api("/rider/location", { body: { lat, lng } }).catch(() => {}); }, []);
  useEffect(() => {
    if (!active) { if (watch.current != null) navigator.geolocation.clearWatch(watch.current); watch.current = null; setState("off"); return; }
    if (!navigator.geolocation) { setState("unsupported"); return; }
    setState("asking");
    watch.current = navigator.geolocation.watchPosition((p) => { setState("live"); push(p.coords.latitude, p.coords.longitude); }, (e) => setState(e.code === 1 ? "denied" : "asking"), { enableHighAccuracy: true, maximumAge: 5000, timeout: 20000 });
    return () => { if (watch.current != null) navigator.geolocation.clearWatch(watch.current); };
  }, [active, push]);
  return { state, push };
}

export default function RiderApp() {
  const { user, logout, config } = useAuth(); const [manual, setManual] = useState(false);
  const list = useData(() => api<any[]>("/rider/deliveries?active=true"), []);
  useEffect(() => { const h = setInterval(list.reload, 10000); return () => clearInterval(h); }, [list.reload]);
  const onWay = (list.data || []).some((o) => o.status === "On the Way");
  const loc = useLocationSharing(onWay || manual);
  return <div className="mx-auto flex min-h-full max-w-md flex-col bg-paper">
    <DemoBanner show={config?.demo} />
    <header className="bg-navy px-5 pb-4 pt-4 text-white" style={{ paddingTop: "calc(1rem + env(safe-area-inset-top))" }}>
      <div className="flex items-center justify-between"><Logo light /><button onClick={logout} className="rounded-xl bg-white/10 px-3 py-1.5 text-sm font-semibold">Sign out</button></div>
      <p className="mt-3 text-white/70">Rider</p><h1 className="text-xl font-extrabold">{user?.full_name}</h1>
      <div className="mt-3 flex items-center justify-between rounded-2xl bg-white/10 p-3 text-sm">
        <span>{loc.state === "live" ? "🟢 Sharing your location" : loc.state === "asking" ? "🟡 Finding your location…" : loc.state === "denied" ? "🔴 Location blocked. Allow it in browser settings." : loc.state === "unsupported" ? "Location not supported" : "⚪ Location sharing off"}</span>
        <button className="font-bold underline" onClick={() => setManual(!manual)} disabled={onWay}>{onWay ? "Auto" : manual ? "Turn off" : "Turn on"}</button></div>
    </header>
    <main className="flex-1 p-4"><Routes>
      <Route index element={<Deliveries list={list} />} /><Route path="history" element={<History />} /><Route path="d/:id" element={<Delivery loc={loc} refreshList={list.reload} />} /><Route path="*" element={<Navigate to="/rider" />} /></Routes></main>
    <nav className="sticky bottom-0 grid grid-cols-2 border-t border-slate-200 bg-white text-sm font-bold" style={{ paddingBottom: "env(safe-area-inset-bottom)" }}>
      <Link to="/rider" className="py-3 text-center text-teal-dark">My deliveries</Link><Link to="/rider/history" className="py-3 text-center text-muted">Completed</Link></nav></div>;
}

function Deliveries({ list }: { list: ReturnType<typeof useData<any[]>> }) {
  if (list.loading && !list.data) return <Spinner />; if (list.error) return <ErrorBox message={list.error} retry={list.reload} />;
  if (!list.data?.length) return <Empty title="No deliveries assigned" hint="When the shop assigns you an order, it shows up here." />;
  return <div className="space-y-3"><h2 className="font-extrabold text-navy">Assigned to you</h2>{list.data.map((o) => <Link key={o.id} to={`/rider/d/${o.id}`} className="card block space-y-2 p-4">
    <div className="flex items-center justify-between"><b className="text-navy">{o.number}</b><StatusBadge status={o.status} /></div>
    <div className="text-sm">📍 <b>{dest(o.destination)}</b></div><div className="text-sm text-muted">{o.customer.name} · {o.items.length} item{o.items.length > 1 ? "s" : ""}</div>
    {!o.rider?.accepted && <Badge tone="warn">Tap to accept</Badge>}</Link>)}</div>;
}

function History() {
  const { data, loading } = useData(() => api<any[]>("/rider/deliveries?active=false"), []);
  if (loading) return <Spinner />; const done = (data || []).filter((o) => ["Delivered", "Cancelled"].includes(o.status));
  return !done.length ? <Empty title="No completed deliveries yet" /> : <div className="space-y-3"><h2 className="font-extrabold text-navy">Completed</h2>{done.map((o) => <div key={o.id} className="card p-4 text-sm">
    <div className="flex justify-between"><b className="text-navy">{o.number}</b><StatusBadge status={o.status} /></div><div className="text-muted">{dest(o.destination)} · {fmtDate(o.created_at)}</div></div>)}</div>;
}

function Delivery({ loc, refreshList }: { loc: ReturnType<typeof useLocationSharing>; refreshList: () => void }) {
  const { id } = useParams(); const nav = useNavigate(); const toast = useToast(); const { config } = useAuth();
  const { data: o, loading, error, reload, setData } = useData(() => api<any>(`/rider/deliveries/${id}`), [id]);
  const [trk, setTrk] = useState<any>(null); const [failing, setFailing] = useState(false); const [reason, setReason] = useState(""); const [busy, setBusy] = useState(false); const sim = useRef(0);
  useEffect(() => { if (id) api(`/rider/deliveries/${id}/tracking`).then(setTrk).catch(() => {}); }, [id, o?.status]);
  const pins = useMemo<Pin[]>(() => { const p: Pin[] = []; if (trk?.shop) p.push({ lat: trk.shop.latitude, lng: trk.shop.longitude, label: "Pick up here", color: "#17324D", glyph: "S" });
    if (trk?.rider_position) p.push({ lat: trk.rider_position.latitude, lng: trk.rider_position.longitude, label: "You", color: "#16A6A0", glyph: "R", pulse: true });
    if (trk?.destination) p.push({ lat: trk.destination.latitude, lng: trk.destination.longitude, label: "Customer", color: "#F0A43A", glyph: "★" }); return p; }, [trk]);
  if (loading && !o) return <Spinner />; if (error || !o) return <ErrorBox message={error || "Not found"} retry={reload} />;
  const act = async (path: string, ok: string, body?: any) => { setBusy(true); try { const r = await api(`/rider/deliveries/${id}/${path}`, { body: body ?? {} }); setData(r); toast(ok); refreshList(); api(`/rider/deliveries/${id}/tracking`).then(setTrk).catch(() => {}); } catch (e: any) { toast(e.message, "err"); } finally { setBusy(false); } };
  /** Demo only: walk the rider from the shop toward the customer so the live tracker can be seen without a phone GPS. */
  const simulate = () => { if (!trk?.shop || !trk?.destination) { toast("Locations are not set for this order", "err"); return; } sim.current = Math.min(1, sim.current + 0.25);
    const lat = trk.shop.latitude + (trk.destination.latitude - trk.shop.latitude) * sim.current; const lng = trk.shop.longitude + (trk.destination.longitude - trk.shop.longitude) * sim.current;
    api("/rider/location", { body: { lat, lng } }).then(() => { toast(`Simulated position ${Math.round(sim.current * 100)}% of the way`); api(`/rider/deliveries/${id}/tracking`).then(setTrk); }); };
  const accepted = !!o.rider?.accepted; const closed = ["Delivered", "Cancelled"].includes(o.status);
  return <div className="space-y-4 pb-6">
    <div className="flex items-center gap-2"><button onClick={() => nav("/rider")} className="grid h-10 w-10 place-items-center rounded-full bg-white text-xl shadow-card" aria-label="Back">‹</button><h1 className="flex-1 text-xl font-extrabold text-navy">{o.number}</h1><StatusBadge status={o.status} /></div>
    <section className="card space-y-2 p-4"><div className="text-xs font-bold uppercase text-muted">Deliver to</div><div className="text-lg font-extrabold text-navy">{dest(o.destination)}</div>
      {o.instructions && <p className="rounded-xl bg-amber-50 p-2 text-sm text-amber-900">“{o.instructions}”</p>}
      <div className="flex items-center justify-between rounded-2xl bg-slate-50 p-3"><div><div className="font-bold text-navy">{o.customer.name}</div><div className="text-sm text-muted">{localPhone(o.customer.phone)}</div></div>
        <a href={`tel:${o.customer.phone}`} className="btn btn-primary px-4 py-2">📞 Call</a></div>
      <a href={navUrl(o, trk)} target="_blank" rel="noreferrer" className="btn btn-navy w-full">🧭 Navigate to customer</a></section>
    {pins.length > 0 && <MapView pins={pins} height={220} />}
    <section className="card space-y-2 p-4"><div className="font-extrabold text-navy">Order</div>{o.items.map((i: any) => <div key={i.id} className="flex justify-between text-sm"><span>{i.quantity} × {i.name}</span><span className="text-muted">{i.line_total != null ? money(i.line_total) : "—"}</span></div>)}
      <div className="border-t border-slate-100 pt-2 text-sm text-muted">Paid online. Collect nothing from the customer.</div>
      <div className="text-sm text-muted">Shop: {o.shop.name} · {o.shop.location} · {o.shop.phones.map(localPhone).join(", ")}</div></section>
    {o.failed_reason && <p className="rounded-xl bg-red-50 p-3 text-sm text-bad">Last attempt reported: {o.failed_reason}</p>}
    {!closed && <div className="space-y-2">
      {!accepted && <button className="btn btn-primary w-full" disabled={busy} onClick={() => act("accept", "Delivery accepted")}>Accept delivery</button>}
      {accepted && o.status !== "On the Way" && <button className="btn btn-primary w-full" disabled={busy || o.status === "Accepted"} onClick={() => act("pickup", "Marked as picked up")}>{o.status === "Accepted" ? "Wait: shop is still preparing" : "I've picked up the order"}</button>}
      {o.status === "On the Way" && <><button className="btn btn-primary w-full" disabled={busy} onClick={() => act("delivered", "Delivered. Well done!")}>Mark as delivered</button>
        <button className="btn btn-danger w-full" onClick={() => setFailing(true)}>Couldn't deliver</button></>}
      {config?.demo && o.status === "On the Way" && <button className="btn btn-ghost w-full text-sm" onClick={simulate}>Demo: simulate moving toward the customer</button>}</div>}
    <Sheet open={failing} onClose={() => setFailing(false)} title="Report unsuccessful attempt"><div className="space-y-3">
      <div className="flex flex-wrap gap-2">{["Customer not reachable", "Customer not at location", "Wrong address"].map((r) => <button key={r} className="chip" onClick={() => setReason(r)}>{r}</button>)}</div>
      <Field label="What happened?"><input className="input" value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
      <button className="btn btn-danger w-full" disabled={reason.length < 3 || busy} onClick={async () => { await act("failed", "Reported to the shop and customer", { reason }); setFailing(false); }}>Send report</button></div></Sheet>
  </div>;
}
