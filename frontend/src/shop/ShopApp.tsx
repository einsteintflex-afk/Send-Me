import { FormEvent, useEffect, useMemo, useState } from "react";
import { Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { api, assetUrl, fmtDate, fmtTime, localPhone, money } from "../api";
import { useAuth } from "../auth";
import MapView, { Pin } from "../MapView";
import { Stat, StaffShell, SectionTitle, Toggle } from "../staff";
import { Badge, Empty, ErrorBox, Field, PayBadge, ProductImage, Sheet, Spinner, StatusBadge, useData, useToast } from "../ui";

const STATUS = ["Pending", "Accepted", "Shopping", "On the Way", "Delivered", "Cancelled"];

/** Super admins open the shop dashboard for one shop at a time; shop staff are fixed to their own shop. */
function useScope() {
  const { user } = useAuth();
  const shops = useData(() => (user?.role === "super_admin" ? api<any[]>("/admin/shops") : Promise.resolve([])), [user?.id]);
  const [pick, setPick] = useState<number | null>(null);
  useEffect(() => { if (shops.data?.length && pick == null) setPick(shops.data[0].id); }, [shops.data, pick]);
  const q = user?.role === "super_admin" ? (pick ? `shop_id=${pick}` : null) : "";
  const url = (p: string) => (q ? p + (p.includes("?") ? "&" : "?") + q : p);
  return { ready: q !== null, url, shops: shops.data || [], pick, setPick, isAdmin: user?.role === "super_admin" };
}

export default function ShopApp() {
  const sc = useScope();
  const ov = useData(() => (sc.ready ? api<any>(sc.url("/shop/overview")) : Promise.resolve(null)), [sc.ready, sc.pick]);
  useEffect(() => { const h = setInterval(ov.reload, 20000); return () => clearInterval(h); }, [ov.reload]);
  const newOrders = ov.data?.by_status?.Pending || 0; const openReq = ov.data?.open_requests || 0;
  const picker = sc.isAdmin && sc.shops.length > 0 && <select aria-label="Shop" className="rounded-xl bg-white/10 px-2 py-1.5 text-sm font-semibold text-white" value={sc.pick ?? ""} onChange={(e) => sc.setPick(+e.target.value)}>
    {sc.shops.map((s) => <option key={s.id} value={s.id} className="text-ink">{s.name}</option>)}</select>;
  return <StaffShell title="Shop dashboard" right={picker || undefined} nav={[{ to: "/shop", label: "Overview", end: true }, { to: "/shop/orders", label: "Orders", badge: newOrders }, { to: "/shop/products", label: "Products" },
    { to: "/shop/requests", label: "Item requests", badge: openReq }, { to: "/shop/settings", label: "Settings" }]}>
    {!sc.ready ? <Spinner /> : <Routes key={sc.pick ?? 0}>
      <Route index element={<Overview ov={ov} />} /><Route path="orders" element={<Orders sc={sc} />} /><Route path="products" element={<Products sc={sc} />} />
      <Route path="requests" element={<Requests sc={sc} />} /><Route path="settings" element={<Settings sc={sc} />} /><Route path="*" element={<Navigate to="/shop" />} /></Routes>}
  </StaffShell>;
}

function Overview({ ov }: { ov: ReturnType<typeof useData<any>> }) {
  const nav = useNavigate(); const d = ov.data;
  if (ov.loading && !d) return <Spinner />; if (ov.error) return <ErrorBox message={ov.error} retry={ov.reload} />; if (!d) return null;
  return <div>
    {(d.by_status.Pending > 0 || d.open_requests > 0) && <div className="mb-4 rounded-2xl bg-amber-100 p-4 font-semibold text-amber-900">
      {d.by_status.Pending > 0 && <button className="mr-4 underline" onClick={() => nav("/shop/orders")}>{d.by_status.Pending} new order{d.by_status.Pending > 1 ? "s" : ""} waiting</button>}
      {d.open_requests > 0 && <button className="underline" onClick={() => nav("/shop/requests")}>{d.open_requests} item request{d.open_requests > 1 ? "s" : ""} need a price</button>}</div>}
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
      <Stat label="Total orders" value={d.total_orders} onClick={() => nav("/shop/orders")} /><Stat label="Pending" value={d.by_status.Pending} tone="warn" onClick={() => nav("/shop/orders")} />
      <Stat label="Accepted" value={d.by_status.Accepted} tone="teal" /><Stat label="Being prepared" value={d.by_status.Shopping} tone="teal" />
      <Stat label="On the way" value={d.by_status["On the Way"]} /><Stat label="Delivered" value={d.by_status.Delivered} tone="ok" />
      <Stat label="Cancelled" value={d.by_status.Cancelled} tone="bad" /><Stat label="Revenue (paid)" value={money(d.revenue)} tone="ok" /></div>
    <SectionTitle>Recent transactions</SectionTitle>
    <div className="card divide-y divide-slate-100">{d.recent_transactions.length === 0 ? <p className="p-5 text-center text-sm text-muted">No payments yet.</p> : d.recent_transactions.map((t: any) =>
      <div key={t.reference} className="flex items-center justify-between p-4 text-sm"><div><b className="text-navy">{t.reference}</b><div className="text-muted">{t.channel || "—"} · {fmtDate(t.at)}</div></div><b className="tabular-nums text-ok">{money(t.amount)}</b></div>)}</div>
    {d.low_stock.length > 0 && <><SectionTitle>Low stock</SectionTitle><div className="card divide-y divide-slate-100">{d.low_stock.map((p: any) => <div key={p.id} className="flex justify-between p-4 text-sm"><span>{p.name}</span><Badge tone="warn">{p.stock_qty} left</Badge></div>)}</div></>}
  </div>;
}

function Orders({ sc }: { sc: ReturnType<typeof useScope> }) {
  const [f, setF] = useState(""); const [open, setOpen] = useState<number | null>(null);
  const { data, loading, error, reload } = useData(() => api<any[]>(sc.url("/shop/orders" + (f ? `?status=${encodeURIComponent(f)}` : ""))), [f]);
  useEffect(() => { const h = setInterval(reload, 15000); return () => clearInterval(h); }, [reload]);
  return <div className="space-y-4">
    <div className="flex gap-2 overflow-x-auto"><button className={`chip ${!f ? "chip-on" : ""}`} onClick={() => setF("")}>All</button>{STATUS.map((s) => <button key={s} className={`chip ${f === s ? "chip-on" : ""}`} onClick={() => setF(s)}>{s}</button>)}</div>
    {loading && !data ? <Spinner /> : error ? <ErrorBox message={error} retry={reload} /> : !data?.length ? <Empty title="No orders here" hint="New paid orders appear automatically." /> :
      <div className="grid gap-3 md:grid-cols-2">{data.map((o) => <button key={o.id} onClick={() => setOpen(o.id)} className="card space-y-2 p-4 text-left transition hover:-translate-y-0.5">
        <div className="flex items-center justify-between"><b className="text-navy">{o.number}</b><StatusBadge status={o.status} /></div>
        <div className="text-sm text-muted">{o.customer.name} · {fmtDate(o.created_at)}</div>
        <p className="line-clamp-2 text-sm">{o.items.map((i: any) => `${i.quantity}× ${i.name}`).join(", ")}</p>
        <div className="flex justify-between text-sm"><span className="text-muted">{o.destination.kind === "hostel" ? `${o.destination.hostel}, Rm ${o.destination.room}` : o.destination.place}</span><b className="tabular-nums">{money(o.total)}</b></div>
        {o.status === "Pending" && <Badge tone="warn">Needs your response</Badge>}</button>)}</div>}
    <OrderSheet sc={sc} id={open} onClose={() => { setOpen(null); reload(); }} />
  </div>;
}

function OrderSheet({ sc, id, onClose }: { sc: ReturnType<typeof useScope>; id: number | null; onClose: () => void }) {
  const toast = useToast();
  const { data: o, reload, setData } = useData(() => (id ? api<any>(sc.url(`/shop/orders/${id}`)) : Promise.resolve(null)), [id]);
  const riders = useData(() => (id ? api<any[]>(sc.url("/shop/riders")) : Promise.resolve([])), [id]);
  const trk = useData(() => (id ? api<any>(sc.url(`/shop/orders/${id}/tracking`)) : Promise.resolve(null)), [id, o?.status]);
  const [rider, setRider] = useState(""); const [reason, setReason] = useState(""); const [rejecting, setRejecting] = useState(false); const [busy, setBusy] = useState(false);
  useEffect(() => { if (o?.status !== "On the Way") return; const h = setInterval(trk.reload, 8000); return () => clearInterval(h); }, [o?.status]); // eslint-disable-line
  const run = async (fn: () => Promise<any>, ok: string) => { setBusy(true); try { const r = await fn(); if (r?.id) setData(r); toast(ok); trk.reload(); } catch (e: any) { toast(e.message, "err"); } finally { setBusy(false); } };
  const setStatus = (status: string, note?: string) => run(() => api(sc.url(`/shop/orders/${id}/status`), { body: { status, note } }), `Order ${status.toLowerCase()}`);
  const pins = useMemo<Pin[]>(() => { const t = trk.data; if (!t) return []; const p: Pin[] = [];
    if (t.shop) p.push({ lat: t.shop.latitude, lng: t.shop.longitude, label: "Shop", color: "#17324D", glyph: "S" });
    if (t.rider_position) p.push({ lat: t.rider_position.latitude, lng: t.rider_position.longitude, label: t.rider?.name || "Rider", color: "#16A6A0", glyph: "R", pulse: true });
    if (t.destination) p.push({ lat: t.destination.latitude, lng: t.destination.longitude, label: "Customer", color: "#F0A43A", glyph: "★" }); return p; }, [trk.data]);
  return <Sheet open={!!id} onClose={onClose} title={o?.number || "Order"}>
    {!o ? <Spinner /> : <div className="space-y-4">
      <div className="flex items-center gap-2"><StatusBadge status={o.status} /><PayBadge s={o.payment_status} /><span className="text-sm text-muted">{fmtDate(o.created_at)}</span></div>
      <div className="rounded-2xl bg-slate-50 p-3 text-sm"><b className="text-navy">{o.customer.name}</b> · <a className="font-semibold text-teal-dark" href={`tel:${o.customer.phone}`}>{localPhone(o.customer.phone)}</a>
        <div className="mt-1">📍 {o.destination.kind === "hostel" ? [o.destination.hostel, o.destination.block && `Block ${o.destination.block}`, `Room ${o.destination.room}`].filter(Boolean).join(", ") : o.destination.place}</div>
        {o.instructions && <div className="mt-1 text-amber-800">“{o.instructions}”</div>}</div>
      <div className="space-y-1.5">{o.items.map((i: any) => <div key={i.id} className={`flex justify-between gap-2 text-sm ${i.is_request ? "rounded-xl bg-amber-50 p-2" : ""}`}><span>{i.quantity} × {i.name}{i.is_request && <em className="text-amber-800"> · requested</em>}</span><span className="tabular-nums">{i.line_total != null ? money(i.line_total) : "price pending"}</span></div>)}
        <div className="flex justify-between border-t border-slate-100 pt-1 text-sm"><span className="text-muted">Delivery{o.delivery_distance_km != null ? ` (${o.delivery_distance_km} km)` : ""}</span><span className="tabular-nums">{money(o.delivery_fee)}</span></div>
        <div className="flex justify-between font-extrabold text-navy"><span>Total paid</span><span className="tabular-nums">{money(o.total)}</span></div></div>
      {o.items.some((i: any) => i.needs_confirmation) && <p className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900">This order has requested items. Send their prices from <b>Item requests</b>.</p>}
      {o.status === "Pending" && (rejecting ? <div className="space-y-2"><Field label="Reason for rejecting (the student sees this)"><input className="input" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Out of stock" /></Field>
        <div className="flex gap-2"><button className="btn btn-danger flex-1" disabled={busy || !reason} onClick={() => setStatus("Cancelled", reason)}>Reject order</button><button className="btn btn-ghost" onClick={() => setRejecting(false)}>Back</button></div></div>
        : <div className="flex gap-2"><button className="btn btn-primary flex-1" disabled={busy} onClick={() => setStatus("Accepted")}>Accept order</button><button className="btn btn-danger" onClick={() => setRejecting(true)}>Reject</button></div>)}
      {o.status === "Accepted" && <div className="flex gap-2"><button className="btn btn-primary flex-1" disabled={busy} onClick={() => setStatus("Shopping")}>Start preparing</button><button className="btn btn-danger" onClick={() => setStatus("Cancelled", "Cancelled by shop")}>Cancel</button></div>}
      {["Accepted", "Shopping", "On the Way"].includes(o.status) && <div className="rounded-2xl border border-slate-200 p-3"><div className="mb-2 text-sm font-bold text-navy">Delivery rider</div>
        {o.rider && <p className="mb-2 text-sm">{o.rider.name} · {localPhone(o.rider.phone)} · <Badge tone={o.rider.accepted ? "ok" : "warn"}>{o.rider.accepted ? "accepted" : "not accepted yet"}</Badge></p>}
        {o.status !== "On the Way" && <div className="flex gap-2"><select className="input" value={rider} onChange={(e) => setRider(e.target.value)} aria-label="Choose rider"><option value="">{o.rider ? "Change rider…" : "Choose rider…"}</option>{riders.data?.map((r) => <option key={r.id} value={r.id}>{r.name} ({localPhone(r.phone)})</option>)}</select>
          <button className="btn btn-navy" disabled={!rider || busy} onClick={() => run(() => api(sc.url(`/shop/orders/${id}/assign`), { body: { rider_id: +rider } }), "Rider assigned")}>Assign</button></div>}
        {riders.data?.length === 0 && <p className="text-sm text-muted">No riders yet. Ask the Send Me admin to add one.</p>}</div>}
      {o.status === "Shopping" && <button className="btn btn-navy w-full" disabled={busy || !o.rider} onClick={() => setStatus("On the Way")}>{o.rider ? "Hand to rider (On the Way)" : "Assign a rider first"}</button>}
      {o.status === "On the Way" && <button className="btn btn-ghost w-full" disabled={busy} onClick={() => setStatus("Delivered")}>Mark delivered (if rider can't)</button>}
      {["On the Way", "Shopping", "Accepted"].includes(o.status) && o.rider && <div><div className="mb-1 text-sm font-bold text-navy">Delivery monitor</div>
        {pins.length ? <MapView pins={pins} height={200} /> : <p className="text-sm text-muted">Map needs the shop and hostel locations (Admin &gt; Delivery).</p>}
        {trk.data?.live && <p className="mt-1 text-sm">{trk.data.rider_position ? <span className={trk.data.rider_position.stale ? "text-amber-700" : "text-ok"}>Rider location {trk.data.rider_position.stale ? "out of date" : "live"} · {fmtTime(trk.data.rider_position.updated_at)}{trk.data.distance_to_destination_km != null && ` · ${trk.data.distance_to_destination_km} km to customer`}</span> : "Waiting for the rider's location…"}</p>}</div>}
      <div className="border-t border-slate-100 pt-3"><div className="mb-1 text-xs font-bold uppercase text-muted">History</div>{o.timeline.map((t: any, i: number) => <div key={i} className="flex justify-between text-sm"><span>{t.status}{t.note && <span className="text-muted"> · {t.note}</span>}</span><span className="text-muted">{fmtTime(t.at)}</span></div>)}</div>
    </div>}</Sheet>;
}

function Products({ sc }: { sc: ReturnType<typeof useScope> }) {
  const toast = useToast();
  const { data, loading, error, reload, setData } = useData(() => api<any[]>(sc.url("/shop/products")), []);
  const cats = useData(() => api<any[]>("/categories"), []);
  const [q, setQ] = useState(""); const [cat, setCat] = useState(""); const [edit, setEdit] = useState<any | null | "new">(null);
  const list = useMemo(() => (data || []).filter((p) => p.active && (!cat || p.category === cat) && (!q || p.name.toLowerCase().includes(q.toLowerCase()))), [data, q, cat]);
  const quick = async (p: any, body: any) => { try { const r = await api(sc.url(`/shop/products/${p.id}`), { method: "PATCH", body }); setData((data || []).map((x) => (x.id === p.id ? { ...x, ...r } : x))); } catch (e: any) { toast(e.message, "err"); reload(); } };
  return <div className="space-y-4">
    <div className="flex flex-wrap gap-2"><input className="input max-w-xs flex-1" placeholder="Search products" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search products" />
      <select className="input w-auto" value={cat} onChange={(e) => setCat(e.target.value)} aria-label="Category"><option value="">All categories</option>{cats.data?.map((c) => <option key={c.id} value={c.slug}>{c.name}</option>)}</select>
      <button className="btn btn-primary" onClick={() => setEdit("new")}>＋ Add product</button></div>
    {loading && !data ? <Spinner /> : error ? <ErrorBox message={error} retry={reload} /> :
      <div className="card divide-y divide-slate-100">{list.map((p) => <div key={p.id} className="flex flex-wrap items-center gap-3 p-3">
        <ProductImage name={p.name} category={p.category} url={p.image_url} className="h-12 w-12 flex-none rounded-xl" />
        <button className="min-w-0 flex-1 text-left" onClick={() => setEdit(p)}><div className="truncate font-bold text-navy">{p.name}</div><div className="text-xs text-muted">{p.category_name}{p.stock_qty != null ? ` · stock ${p.stock_qty}` : " · stock not tracked"}{p.stock_qty != null && p.low_stock_threshold != null && p.stock_qty <= p.low_stock_threshold && <span className="ml-1 font-bold text-amber-700">LOW</span>}</div></button>
        <label className="flex items-center gap-1 text-sm"><span className="text-muted">GH₵</span><input className="input w-24 px-2 py-1.5 text-right tabular-nums" defaultValue={p.price ?? ""} placeholder="—" inputMode="decimal" aria-label={`Price for ${p.name}`}
          onBlur={(e) => { const v = e.target.value.trim(); if (v !== String(p.price ?? "") && v !== "" && !isNaN(+v)) quick(p, { price: v }); }} /></label>
        <div className="flex items-center gap-2"><Toggle on={p.availability === "available"} label={`${p.name} available`} onChange={(v) => quick(p, { availability: v ? "available" : "unavailable" })} /><span className="w-20 text-xs font-bold text-muted">{p.availability === "available" ? "Available" : "Unavailable"}</span></div></div>)}
        {list.length === 0 && <p className="p-6 text-center text-sm text-muted">No products match.</p>}</div>}
    <ProductSheet sc={sc} product={edit} cats={cats.data || []} onClose={() => setEdit(null)} onSaved={() => { setEdit(null); reload(); }} />
  </div>;
}

function ProductSheet({ sc, product, cats, onClose, onSaved }: any) {
  const toast = useToast(); const isNew = product === "new";
  const blank = { name: "", category: "drinks", description: "", price: "", availability: "available", stock_qty: "", low_stock_threshold: "", featured: false, variants: [] as any[] };
  const [f, setF] = useState<any>(blank); const [busy, setBusy] = useState(false);
  useEffect(() => { if (!product) return; setF(isNew ? blank : { ...blank, ...product, price: product.price ?? "", stock_qty: product.stock_qty ?? "", low_stock_threshold: product.low_stock_threshold ?? "", description: product.description ?? "",
    variants: (product.variants || []).map((v: any) => ({ name: v.name, price: v.price ?? "", availability: v.availability, stock_qty: "" })) }); }, [product]); // eslint-disable-line
  const num = (v: any) => (v === "" || v == null ? null : v);
  const save = async (e: FormEvent) => { e.preventDefault(); setBusy(true);
    const body = { name: f.name, category: f.category, description: f.description || null, price: num(f.price), availability: f.availability, stock_qty: num(f.stock_qty) == null ? null : +f.stock_qty,
      low_stock_threshold: num(f.low_stock_threshold) == null ? null : +f.low_stock_threshold, featured: !!f.featured, variants: f.variants.map((v: any) => ({ name: v.name, price: num(v.price), availability: v.availability, stock_qty: num(v.stock_qty) == null ? null : +v.stock_qty })) };
    try { isNew ? await api(sc.url("/shop/products"), { body }) : await api(sc.url(`/shop/products/${product.id}`), { method: "PUT", body }); toast("Product saved"); onSaved(); } catch (x: any) { toast(x.message, "err"); } finally { setBusy(false); } };
  const upload = async (file?: File) => { if (!file || isNew) return; const fd = new FormData(); fd.append("file", file); try { await api(sc.url(`/shop/products/${product.id}/image`), { form: fd }); toast("Photo uploaded"); onSaved(); } catch (x: any) { toast(x.message, "err"); } };
  const remove = async () => { try { await api(sc.url(`/shop/products/${product.id}`), { method: "DELETE" }); toast("Product removed from the shop"); onSaved(); } catch (x: any) { toast(x.message, "err"); } };
  return <Sheet open={!!product} onClose={onClose} title={isNew ? "Add product" : "Edit product"}>
    <form onSubmit={save} className="space-y-3">
      <Field label="Product name"><input className="input" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} required /></Field>
      <div className="grid grid-cols-2 gap-3"><Field label="Category"><select className="input" value={f.category} onChange={(e) => setF({ ...f, category: e.target.value })}>{cats.map((c: any) => <option key={c.id} value={c.slug}>{c.name}</option>)}</select></Field>
        <Field label="Price (GH₵)" hint="Leave empty if unknown. It can't be ordered until priced."><input className="input" inputMode="decimal" value={f.price} onChange={(e) => setF({ ...f, price: e.target.value })} /></Field></div>
      <Field label="Description"><textarea className="input" rows={2} value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} /></Field>
      <div className="grid grid-cols-2 gap-3"><Field label="Stock quantity" hint="Empty = not tracked"><input className="input" inputMode="numeric" value={f.stock_qty} onChange={(e) => setF({ ...f, stock_qty: e.target.value })} /></Field>
        <Field label="Low-stock alert at"><input className="input" inputMode="numeric" value={f.low_stock_threshold} onChange={(e) => setF({ ...f, low_stock_threshold: e.target.value })} /></Field></div>
      <div className="flex items-center justify-between"><span className="font-semibold text-navy">Available to order</span><Toggle on={f.availability === "available"} label="Available" onChange={(v) => setF({ ...f, availability: v ? "available" : "unavailable" })} /></div>
      <div className="flex items-center justify-between"><span className="font-semibold text-navy">Featured on home</span><Toggle on={f.featured} label="Featured" onChange={(v) => setF({ ...f, featured: v })} /></div>
      <div><div className="mb-1 flex items-center justify-between"><span className="label mb-0">Options (sizes, packs)</span><button type="button" className="text-sm font-bold text-teal-dark" onClick={() => setF({ ...f, variants: [...f.variants, { name: "", price: "", availability: "available", stock_qty: "" }] })}>＋ Add option</button></div>
        {f.variants.map((v: any, i: number) => <div key={i} className="mb-2 flex gap-2"><input className="input" placeholder="e.g. 1 litre" value={v.name} onChange={(e) => { const a = [...f.variants]; a[i] = { ...v, name: e.target.value }; setF({ ...f, variants: a }); }} required />
          <input className="input w-28" placeholder="Price" inputMode="decimal" value={v.price} onChange={(e) => { const a = [...f.variants]; a[i] = { ...v, price: e.target.value }; setF({ ...f, variants: a }); }} />
          <button type="button" className="px-2 text-bad" aria-label="Remove option" onClick={() => setF({ ...f, variants: f.variants.filter((_: any, j: number) => j !== i) })}>×</button></div>)}</div>
      {!isNew && <Field label="Photo"><div className="flex items-center gap-3">{product?.image_url && <img className="h-14 w-14 rounded-xl object-cover" src={assetUrl(product.image_url)!} alt="" />}<input type="file" accept="image/jpeg,image/png,image/webp" onChange={(e) => upload(e.target.files?.[0])} className="text-sm" /></div></Field>}
      <button className="btn btn-primary w-full" disabled={busy}>{busy ? "Saving…" : "Save product"}</button>
      {!isNew && <button type="button" className="btn btn-danger w-full" onClick={remove}>Remove from shop</button>}</form></Sheet>;
}

function Requests({ sc }: { sc: ReturnType<typeof useScope> }) {
  const toast = useToast(); const [f, setF] = useState("submitted");
  const { data, loading, error, reload } = useData(() => api<any[]>(sc.url("/shop/requests" + (f ? `?status=${f}` : ""))), [f]);
  useEffect(() => { const h = setInterval(reload, 10000); return () => clearInterval(h); }, [reload]);
  const [price, setPrice] = useState<Record<number, string>>({}); const [note, setNote] = useState<Record<number, string>>({});
  const respond = async (r: any, accept: boolean) => { try { await api(sc.url(`/shop/requests/${r.id}/respond`), { body: { accept, unit_price: accept ? price[r.id] : null, note: note[r.id] || null } }); toast(accept ? "Price sent to the student" : "Request declined"); reload(); } catch (e: any) { toast(e.message, "err"); } };
  return <div className="space-y-4">
    <div className="flex gap-2 overflow-x-auto">{[["submitted", "Needs price"], ["priced", "Price sent"], ["approved", "Approved"], ["rejected", "Rejected"], ["", "All"]].map(([v, l]) => <button key={v} className={`chip ${f === v ? "chip-on" : ""}`} onClick={() => setF(v)}>{l}</button>)}</div>
    {loading && !data ? <Spinner /> : error ? <ErrorBox message={error} retry={reload} /> : !data?.length ? <Empty title="No requests here" hint="When a student asks for an item that isn't listed, it appears here and you're alerted." /> :
      <div className="grid gap-3 md:grid-cols-2">{data.map((r) => <div key={r.id} className="card space-y-3 p-4">
        <div className="flex items-start justify-between gap-2"><div><b className="text-navy">{r.quantity} × {r.name}</b>{r.brand && <span className="text-sm text-muted"> · {r.brand}</span>}<div className="text-sm text-muted">from {r.student}</div></div><Badge tone={r.status === "submitted" ? "warn" : r.status === "rejected" ? "bad" : "ok"}>{r.status === "submitted" ? "needs price" : r.status}</Badge></div>
        {r.description && <p className="text-sm">{r.description}</p>}{r.image_url && <img src={assetUrl(r.image_url)!} alt="Reference" className="h-32 rounded-xl object-cover" />}
        {r.confirmed_unit_price != null && <p className="text-sm font-semibold text-ok">Price sent: {money(r.confirmed_unit_price)} each{r.order_id && " · student must approve & pay"}</p>}
        {["submitted", "priced"].includes(r.status) && <div className="space-y-2"><div className="flex gap-2"><div className="relative flex-1"><span className="absolute left-3 top-3 text-muted">GH₵</span><input className="input pl-14" inputMode="decimal" placeholder="Price each" value={price[r.id] ?? ""} onChange={(e) => setPrice({ ...price, [r.id]: e.target.value })} aria-label={`Price for ${r.name}`} /></div>
          <button className="btn btn-primary" disabled={!price[r.id]} onClick={() => respond(r, true)}>Send price</button></div>
          <input className="input" placeholder="Note to student (optional)" value={note[r.id] ?? ""} onChange={(e) => setNote({ ...note, [r.id]: e.target.value })} />
          <button className="btn btn-danger w-full py-2 text-sm" onClick={() => respond(r, false)}>We can't supply this</button></div>}</div>)}</div>}
  </div>;
}

function Settings({ sc }: { sc: ReturnType<typeof useScope> }) {
  const toast = useToast(); const { data, loading, reload } = useData(() => api<any>(sc.url("/shop/settings")), []);
  const [f, setF] = useState<any>(null); const [hours, setHours] = useState("");
  useEffect(() => { if (data) { setF({ ...data, phones: data.phones.join(", ") }); setHours(Object.entries(data.opening_hours || {}).map(([k, v]) => `${k}: ${v}`).join("\n")); } }, [data]);
  if (loading || !f) return <Spinner />;
  const save = async (e: FormEvent) => { e.preventDefault(); const oh: Record<string, string> = {}; hours.split("\n").forEach((l) => { const i = l.indexOf(":"); if (i > 0) oh[l.slice(0, i).trim()] = l.slice(i + 1).trim(); });
    try { await api(sc.url("/shop/settings"), { method: "PATCH", body: { name: f.name, location: f.location, phones: f.phones.split(",").map((x: string) => x.trim()).filter(Boolean), opening_hours: oh,
      delivery_estimate_minutes: f.delivery_estimate_minutes ? +f.delivery_estimate_minutes : null, accepting_orders: f.accepting_orders } }); toast("Settings saved"); reload(); } catch (x: any) { toast(x.message, "err"); } };
  return <form onSubmit={save} className="card mx-auto max-w-xl space-y-4 p-5">
    <div className="flex items-center justify-between rounded-2xl bg-mint p-4"><div><b className="text-navy">Accepting orders</b><div className="text-sm text-muted">Turn off when the shop is closed.</div></div><Toggle on={f.accepting_orders} label="Accepting orders" onChange={(v) => setF({ ...f, accepting_orders: v })} /></div>
    <Field label="Shop name"><input className="input" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} required /></Field>
    <Field label="Location"><input className="input" value={f.location || ""} onChange={(e) => setF({ ...f, location: e.target.value })} /></Field>
    <Field label="Contact phone numbers" hint="Separate with commas. Format: +233XXXXXXXXX"><input className="input" value={f.phones} onChange={(e) => setF({ ...f, phones: e.target.value })} /></Field>
    <Field label="Typical delivery time (minutes)"><input className="input" inputMode="numeric" value={f.delivery_estimate_minutes ?? ""} onChange={(e) => setF({ ...f, delivery_estimate_minutes: e.target.value })} /></Field>
    <Field label="Opening hours" hint="One per line, e.g. Mon-Fri: 8am-9pm"><textarea className="input" rows={4} value={hours} onChange={(e) => setHours(e.target.value)} /></Field>
    <button className="btn btn-primary w-full">Save settings</button></form>;
}
