import { FormEvent, useEffect, useState } from "react";
import { Link, Navigate, Route, Routes } from "react-router-dom";
import { api, fmtDate, fmtTime, localPhone, money } from "../api";
import MapView, { Pin } from "../MapView";
import { SectionTitle, Stat, StaffShell, Table, Toggle } from "../staff";
import { Badge, Empty, ErrorBox, Field, PayBadge, Sheet, Spinner, StatusBadge, useData, useToast } from "../ui";

const STATUS = ["Pending", "Accepted", "Shopping", "On the Way", "Delivered", "Cancelled"];

export default function AdminApp() {
  const reqs = useData(() => api<any[]>("/admin/requests?status=submitted"), []);
  useEffect(() => { const h = setInterval(reqs.reload, 15000); return () => clearInterval(h); }, [reqs.reload]);
  return <StaffShell title="Administrator" nav={[{ to: "/admin", label: "Overview", end: true }, { to: "/admin/orders", label: "Orders" }, { to: "/admin/payments", label: "Payments" },
    { to: "/admin/requests", label: "Item requests", badge: reqs.data?.length || 0 }, { to: "/admin/shops", label: "Shops" }, { to: "/admin/riders", label: "Riders" }, { to: "/admin/students", label: "Students" },
    { to: "/admin/delivery", label: "Delivery" }, { to: "/admin/catalog", label: "Catalogue & promos" }, { to: "/admin/support", label: "Support" }, { to: "/admin/system", label: "System" }]}>
    <Routes><Route index element={<Overview />} /><Route path="orders" element={<Orders />} /><Route path="payments" element={<Payments />} /><Route path="requests" element={<Requests onChange={reqs.reload} />} />
      <Route path="shops" element={<Shops />} /><Route path="riders" element={<Riders />} /><Route path="students" element={<Students />} /><Route path="delivery" element={<Delivery />} />
      <Route path="catalog" element={<Catalog />} /><Route path="support" element={<Support />} /><Route path="system" element={<System />} /><Route path="*" element={<Navigate to="/admin" />} /></Routes></StaffShell>;
}

function Overview() {
  const rep = useData(() => api<any>("/admin/reports/summary"), []); const shops = useData(() => api<any[]>("/admin/shops"), []); const orders = useData(() => api<any[]>("/admin/orders?limit=8"), []);
  if (rep.loading) return <Spinner />; if (rep.error) return <ErrorBox message={rep.error} retry={rep.reload} />; const r = rep.data!;
  const max = Math.max(1, ...Object.values<number>(r.orders_by_status));
  const barTone: any = { Pending: "bg-warn", Accepted: "bg-teal", Shopping: "bg-teal", "On the Way": "bg-navy", Delivered: "bg-ok", Cancelled: "bg-bad" };
  return <div>
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4"><Stat label="Revenue (paid)" value={money(r.revenue)} tone="ok" /><Stat label="Students" value={r.students} /><Stat label="Refunds to process" value={r.refunds_pending} tone={r.refunds_pending ? "warn" : "navy"} />
      <Stat label="Average rating" value={r.average_rating ? r.average_rating.toFixed(1) + " ★" : "—"} tone="teal" /></div>
    <div className="mt-6 grid gap-4 md:grid-cols-2">
      <div className="card p-5"><h2 className="mb-4 font-extrabold text-navy">Orders by status</h2><div className="space-y-3">{STATUS.map((s) => <div key={s} className="flex items-center gap-3 text-sm"><span className="w-20 text-muted">{s}</span>
        <div className="h-5 flex-1 rounded-full bg-slate-100"><div className={`h-5 rounded-full ${barTone[s]}`} style={{ width: `${(r.orders_by_status[s] / max) * 100}%`, minWidth: r.orders_by_status[s] ? 8 : 0 }} /></div><b className="w-8 text-right tabular-nums">{r.orders_by_status[s]}</b></div>)}</div></div>
      <div className="card p-5"><h2 className="mb-4 font-extrabold text-navy">Sales by shop</h2>{r.per_shop.length === 0 ? <p className="text-sm text-muted">No paid orders yet.</p> : r.per_shop.map((s: any) =>
        <div key={s.shop_id} className="flex justify-between border-b border-slate-100 py-2 text-sm last:border-0"><span>{shops.data?.find((x) => x.id === s.shop_id)?.name || `Shop ${s.shop_id}`}</span><span><b className="tabular-nums">{money(s.revenue)}</b> <span className="text-muted">· {s.orders} orders</span></span></div>)}</div></div>
    <SectionTitle right={<Link className="text-sm font-bold text-teal-dark" to="/admin/orders">All orders</Link>}>Latest orders</SectionTitle>
    <Table head={["Order", "Status", "Payment", "Total"]} rows={(orders.data || []).map((o) => [o.number || `#${o.id}`, <StatusBadge status={o.status} />, <PayBadge s={o.payment_status} />, <b className="tabular-nums">{money(o.total)}</b>])} empty="No orders yet." /></div>;
}

function Orders() {
  const [f, setF] = useState(""); const [open, setOpen] = useState<number | null>(null);
  const { data, loading, error, reload } = useData(() => api<any[]>("/admin/orders?limit=200" + (f ? `&status=${encodeURIComponent(f)}` : "")), [f]);
  return <div className="space-y-4"><div className="flex gap-2 overflow-x-auto"><button className={`chip ${!f ? "chip-on" : ""}`} onClick={() => setF("")}>All</button>{STATUS.map((s) => <button key={s} className={`chip ${f === s ? "chip-on" : ""}`} onClick={() => setF(s)}>{s}</button>)}</div>
    {loading ? <Spinner /> : error ? <ErrorBox message={error} retry={reload} /> : <Table head={["Order", "Status", "Payment", "Total", ""]} rows={(data || []).map((o) => [o.number || `#${o.id}`, <StatusBadge status={o.status} />, <PayBadge s={o.payment_status} />, <b className="tabular-nums">{money(o.total)}</b>, <button className="font-bold text-teal-dark" onClick={() => setOpen(o.id)}>Open</button>])} empty="No orders." />}
    <OrderSheet id={open} onClose={() => setOpen(null)} /></div>;
}
function OrderSheet({ id, onClose }: { id: number | null; onClose: () => void }) {
  const { data: o } = useData(() => (id ? api<any>(`/admin/orders/${id}`) : Promise.resolve(null)), [id]); const { data: t } = useData(() => (id ? api<any>(`/admin/orders/${id}/tracking`) : Promise.resolve(null)), [id]);
  const pins: Pin[] = []; if (t?.shop) pins.push({ lat: t.shop.latitude, lng: t.shop.longitude, label: "Shop", color: "#17324D", glyph: "S" }); if (t?.rider_position) pins.push({ lat: t.rider_position.latitude, lng: t.rider_position.longitude, label: "Rider", color: "#16A6A0", glyph: "R", pulse: true }); if (t?.destination) pins.push({ lat: t.destination.latitude, lng: t.destination.longitude, label: "Customer", color: "#F0A43A", glyph: "★" });
  return <Sheet open={!!id} onClose={onClose} title={o?.number || "Order"}>{!o ? <Spinner /> : <div className="space-y-3 text-sm">
    <div className="flex gap-2"><StatusBadge status={o.status} /><PayBadge s={o.payment_status} /></div>
    <p><b>{o.customer.name}</b> · {localPhone(o.customer.phone)}<br />{o.destination.kind === "hostel" ? `${o.destination.hostel}, Room ${o.destination.room}` : o.destination.place}</p>
    {o.items.map((i: any) => <div key={i.id} className="flex justify-between"><span>{i.quantity} × {i.name}</span><span>{i.line_total != null ? money(i.line_total) : "pending"}</span></div>)}
    <div className="flex justify-between border-t pt-2 font-bold"><span>Total</span><span>{money(o.total)}</span></div>
    <p className="text-muted">Shop: {o.shop.name} · Rider: {o.rider ? `${o.rider.name} (${localPhone(o.rider.phone)})` : "not assigned"}</p>
    {pins.length > 0 && <MapView pins={pins} height={200} />}
    {o.payment_status === "refund_pending" && <p className="rounded-xl bg-amber-50 p-3 text-amber-900">Refund pending. Refund this payment in the Paystack dashboard.</p>}
    <Link to="/shop" className="btn btn-ghost w-full">Manage in shop dashboard</Link></div>}</Sheet>;
}

function Payments() {
  const [f, setF] = useState(""); const { data, loading, error, reload } = useData(() => api<any[]>("/admin/payments?limit=200" + (f ? `&status=${f}` : "")), [f]);
  return <div className="space-y-4"><div className="flex gap-2">{["", "success", "initialized", "failed", "abandoned"].map((s) => <button key={s} className={`chip ${f === s ? "chip-on" : ""}`} onClick={() => setF(s)}>{s || "All"}</button>)}</div>
    {loading ? <Spinner /> : error ? <ErrorBox message={error} retry={reload} /> : <Table head={["Reference", "Order", "Type", "Amount", "Channel", "Status"]} rows={(data || []).map((p) => [<code className="text-xs">{p.reference}</code>, `#${p.order_id}`, p.kind === "order" ? "Order" : "Requested item", <b className="tabular-nums">{money(p.amount)}</b>, p.channel || "—", <Badge tone={p.status === "success" ? "ok" : p.status === "initialized" ? "warn" : "bad"}>{p.status}</Badge>])} empty="No payments yet." />}</div>;
}

function Requests({ onChange }: { onChange: () => void }) {
  const toast = useToast(); const [f, setF] = useState("submitted"); const { data, loading, error, reload } = useData(() => api<any[]>("/admin/requests" + (f ? `?status=${f}` : "")), [f]);
  const [price, setPrice] = useState<Record<number, string>>({});
  const respond = async (r: any, accept: boolean) => { try { await api(`/admin/requests/${r.id}/respond`, { body: { accept, unit_price: accept ? price[r.id] : null } }); toast(accept ? "Price sent to the student" : "Declined"); reload(); onChange(); } catch (e: any) { toast(e.message, "err"); } };
  return <div className="space-y-4"><div className="flex gap-2 overflow-x-auto">{[["submitted", "Needs price"], ["priced", "Price sent"], ["approved", "Approved"], ["rejected", "Rejected"], ["", "All"]].map(([v, l]) => <button key={v} className={`chip ${f === v ? "chip-on" : ""}`} onClick={() => setF(v)}>{l}</button>)}</div>
    {loading ? <Spinner /> : error ? <ErrorBox message={error} retry={reload} /> : !data?.length ? <Empty title="No requests" hint="Students' unlisted-item requests appear here the moment they send them." /> :
      <div className="grid gap-3 md:grid-cols-2">{data.map((r) => <div key={r.id} className="card space-y-2 p-4"><div className="flex justify-between"><b className="text-navy">{r.quantity} × {r.name}</b><Badge tone={r.status === "submitted" ? "warn" : r.status === "rejected" ? "bad" : "ok"}>{r.status}</Badge></div>
        <div className="text-sm text-muted">{r.student}{r.brand && ` · ${r.brand}`}</div>{r.description && <p className="text-sm">{r.description}</p>}
        {r.confirmed_unit_price != null && <p className="text-sm font-semibold text-ok">Price sent: {money(r.confirmed_unit_price)}</p>}
        {["submitted", "priced"].includes(r.status) && <div className="flex gap-2"><input className="input" inputMode="decimal" placeholder="Price each (GH₵)" value={price[r.id] ?? ""} onChange={(e) => setPrice({ ...price, [r.id]: e.target.value })} aria-label={`Price for ${r.name}`} />
          <button className="btn btn-primary" disabled={!price[r.id]} onClick={() => respond(r, true)}>Send</button><button className="btn btn-danger" onClick={() => respond(r, false)}>Decline</button></div>}</div>)}</div>}</div>;
}

function Shops() {
  const toast = useToast(); const shops = useData(() => api<any[]>("/admin/shops"), []); const unis = useData(() => api<any[]>("/universities"), []);
  const [adding, setAdding] = useState(false); const [staffFor, setStaffFor] = useState<any | null>(null);
  const [f, setF] = useState({ campus_id: 0, name: "", slug: "", location: "", phones: "" });
  const submit = async (e: FormEvent) => { e.preventDefault(); try { await api("/admin/shops", { body: { ...f, campus_id: f.campus_id || unis.data?.[0]?.campuses?.[0]?.id, phones: f.phones.split(",").map((x) => x.trim()).filter(Boolean), location: f.location || null } }); toast("Shop created"); setAdding(false); shops.reload(); } catch (x: any) { toast(x.message, "err"); } };
  return <div><SectionTitle right={<button className="btn btn-primary py-2" onClick={() => setAdding(true)}>＋ Register shop</button>}>Participating shops</SectionTitle>
    {shops.loading ? <Spinner /> : <Table head={["Shop", "Location", "Phones", "Open", "Active", ""]} rows={(shops.data || []).map((s) => [<b className="text-navy">{s.name}</b>, s.location || "—", s.phones.map(localPhone).join(", ") || "—", s.accepting_orders ? "Yes" : "No",
      <Toggle on={s.active} label={`${s.name} active`} onChange={(v) => api(`/admin/shops/${s.id}/active`, { body: { active: v } }).then(shops.reload)} />, <button className="font-bold text-teal-dark" onClick={() => setStaffFor(s)}>Staff</button>])} />}
    <Sheet open={adding} onClose={() => setAdding(false)} title="Register a shop"><form onSubmit={submit} className="space-y-3">
      <Field label="Campus"><select className="input" value={f.campus_id} onChange={(e) => setF({ ...f, campus_id: +e.target.value })}>{unis.data?.flatMap((u) => u.campuses.map((c: any) => <option key={c.id} value={c.id}>{u.name} · {c.name}</option>))}</select></Field>
      <Field label="Shop name"><input className="input" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} required /></Field>
      <Field label="Web address" hint="Lowercase letters, numbers, dashes"><input className="input" value={f.slug} onChange={(e) => setF({ ...f, slug: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "-") })} required /></Field>
      <Field label="Location"><input className="input" value={f.location} onChange={(e) => setF({ ...f, location: e.target.value })} /></Field>
      <Field label="Phones (comma separated)"><input className="input" value={f.phones} onChange={(e) => setF({ ...f, phones: e.target.value })} /></Field><button className="btn btn-primary w-full">Create shop</button></form></Sheet>
    <StaffSheet shop={staffFor} onClose={() => setStaffFor(null)} /></div>;
}
function StaffSheet({ shop, onClose }: { shop: any | null; onClose: () => void }) {
  const toast = useToast(); const { data, reload } = useData(() => (shop ? api<any[]>(`/admin/shops/${shop.id}/staff`) : Promise.resolve([])), [shop?.id]);
  const [f, setF] = useState({ full_name: "", email: "", phone: "", password: "", role: "shop_staff" });
  const add = async (e: FormEvent) => { e.preventDefault(); try { await api(`/admin/shops/${shop.id}/staff`, { body: f }); toast("Staff account created"); setF({ full_name: "", email: "", phone: "", password: "", role: "shop_staff" }); reload(); } catch (x: any) { toast(x.message, "err"); } };
  return <Sheet open={!!shop} onClose={onClose} title={`${shop?.name} staff`}><div className="space-y-3">
    {data?.map((u) => <div key={u.id} className="flex justify-between rounded-xl bg-slate-50 p-3 text-sm"><span><b>{u.full_name}</b> · {u.email}</span><Badge>{u.role.replace("_", " ")}</Badge></div>)}
    <form onSubmit={add} className="space-y-3 border-t pt-3"><h3 className="font-bold text-navy">Add staff account</h3>
      <input className="input" placeholder="Full name" value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} required /><input className="input" type="email" placeholder="Email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} required />
      <input className="input" placeholder="Phone" value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} required /><input className="input" type="password" placeholder="Password (8+ characters)" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} required minLength={8} />
      <select className="input" value={f.role} onChange={(e) => setF({ ...f, role: e.target.value })}><option value="shop_staff">Shop staff</option><option value="shop_admin">Shop manager</option></select><button className="btn btn-primary w-full">Create account</button></form></div></Sheet>;
}

function Riders() {
  const toast = useToast(); const riders = useData(() => api<any[]>("/admin/riders"), []); const unis = useData(() => api<any[]>("/universities"), []);
  const [adding, setAdding] = useState(false); const [reset, setReset] = useState<any | null>(null); const [pw, setPw] = useState("");
  const [f, setF] = useState({ full_name: "", phone: "", email: "", password: "", campus_id: 0 });
  const add = async (e: FormEvent) => { e.preventDefault(); try { await api("/admin/riders", { body: { ...f, email: f.email || null, campus_id: f.campus_id || unis.data?.[0]?.campuses?.[0]?.id } }); toast("Rider account created. They sign in with their phone number."); setAdding(false); setF({ full_name: "", phone: "", email: "", password: "", campus_id: 0 }); riders.reload(); } catch (x: any) { toast(x.message, "err"); } };
  return <div><SectionTitle right={<button className="btn btn-primary py-2" onClick={() => setAdding(true)}>＋ Add rider</button>}>Delivery riders</SectionTitle>
    {riders.loading ? <Spinner /> : <Table head={["Name", "Phone (login)", "Last seen", "Active", ""]} rows={(riders.data || []).map((r) => [<b className="text-navy">{r.name}</b>, localPhone(r.phone), r.last_seen_at ? fmtDate(r.last_seen_at) : "never",
      <Toggle on={r.is_active} label={`${r.name} active`} onChange={(v) => api(`/admin/users/${r.id}/active`, { body: { is_active: v } }).then(riders.reload)} />, <button className="font-bold text-teal-dark" onClick={() => { setReset(r); setPw(""); }}>Reset password</button>])} empty="No riders yet. Add your first rider." />}
    <Sheet open={adding} onClose={() => setAdding(false)} title="Add a rider"><form onSubmit={add} className="space-y-3">
      <Field label="Full name"><input className="input" value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} required /></Field>
      <Field label="Phone number" hint="This is how the rider signs in. No email needed."><input className="input" inputMode="tel" value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} required /></Field>
      <Field label="Password" hint="8+ characters. Give it to the rider; they can ask you to reset it."><input className="input" type="text" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} required minLength={8} /></Field>
      <Field label="Email (optional)"><input className="input" type="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></Field>
      <Field label="Campus"><select className="input" value={f.campus_id} onChange={(e) => setF({ ...f, campus_id: +e.target.value })}>{unis.data?.flatMap((u) => u.campuses.map((c: any) => <option key={c.id} value={c.id}>{u.name} · {c.name}</option>))}</select></Field>
      <button className="btn btn-primary w-full">Create rider</button></form></Sheet>
    <Sheet open={!!reset} onClose={() => setReset(null)} title={`Reset password: ${reset?.name}`}><div className="space-y-3"><Field label="New password"><input className="input" value={pw} onChange={(e) => setPw(e.target.value)} minLength={8} /></Field>
      <button className="btn btn-primary w-full" disabled={pw.length < 8} onClick={() => api(`/admin/users/${reset.id}/password`, { body: { password: pw } }).then(() => { toast("Password changed"); setReset(null); }).catch((e) => toast(e.message, "err"))}>Save new password</button></div></Sheet></div>;
}

function Students() {
  const [q, setQ] = useState(""); const { data, loading, reload } = useData(() => api<any[]>(`/admin/users?role=student&limit=200${q ? `&q=${encodeURIComponent(q)}` : ""}`), [q]);
  return <div className="space-y-4"><input className="input max-w-sm" placeholder="Search name, email or phone" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search students" />
    {loading ? <Spinner /> : <Table head={["Name", "Phone", "Email", "Active"]} rows={(data || []).map((u) => [<b className="text-navy">{u.full_name}</b>, localPhone(u.phone), u.email, <Toggle on={u.is_active} label={`${u.full_name} active`} onChange={(v) => api(`/admin/users/${u.id}/active`, { body: { is_active: v } }).then(reload)} />])} empty="No students found." />}</div>;
}

function Delivery() {
  const toast = useToast(); const dist = useData(() => api<any>("/admin/delivery-distance"), []); const flat = useData(() => api<any[]>("/admin/delivery-pricing"), []); const locs = useData(() => api<any>("/admin/locations"), []);
  const [d, setD] = useState({ rate_per_km: "", min_fee: "", travel_mode: "WALK" }); const [fee, setFee] = useState(""); const [edit, setEdit] = useState<Record<string, { latitude: string; longitude: string }>>({}); const [geo, setGeo] = useState<any[] | null>(null);
  useEffect(() => { if (dist.data) setD({ rate_per_km: dist.data.rate_per_km, min_fee: dist.data.min_fee || "", travel_mode: dist.data.travel_mode }); }, [dist.data]);
  useEffect(() => { const g = flat.data?.find((x) => !x.shop_id && !x.campus_id); if (g) setFee(String(g.fee)); }, [flat.data]);
  const saveDist = async (e: FormEvent) => { e.preventDefault(); try { await api("/admin/delivery-distance", { method: "PUT", body: { rate_per_km: d.rate_per_km, min_fee: d.min_fee || null, travel_mode: d.travel_mode } }); toast("Distance pricing saved"); dist.reload(); } catch (x: any) { toast(x.message, "err"); } };
  const saveFee = async (e: FormEvent) => { e.preventDefault(); try { await api("/admin/delivery-pricing", { method: "PUT", body: { fee } }); toast("Flat fee saved"); flat.reload(); } catch (x: any) { toast(x.message, "err"); } };
  const key = (t: string, id: number) => `${t}:${id}`;
  const saveLoc = async (t: string, id: number) => { const v = edit[key(t, id)]; try { await api(`/admin/${t === "shop" ? "shops" : "hostels"}/${id}/location`, { method: "PUT", body: { latitude: +v.latitude, longitude: +v.longitude } }); toast("Location saved"); locs.reload(); } catch (x: any) { toast(x.message, "err"); } };
  const geocode = async (apply: boolean) => { try { setGeo(await api("/admin/geocode", { body: { apply, only_missing: !apply ? false : true } })); if (apply) { toast("Applied"); locs.reload(); } } catch (x: any) { toast(x.message, "err"); } };
  const rows = [...(locs.data?.shops || []).map((s: any) => ({ t: "shop", ...s })), ...(locs.data?.hostels || []).map((h: any) => ({ t: "hostel", ...h }))];
  const pins: Pin[] = rows.filter((r) => r.latitude != null).map((r) => ({ lat: r.latitude, lng: r.longitude, label: r.name, color: r.t === "shop" ? "#17324D" : "#F0A43A", glyph: r.t === "shop" ? "S" : "H" }));
  return <div className="space-y-6">
    <div className="grid gap-4 md:grid-cols-2">
      <form onSubmit={saveDist} className="card space-y-3 p-5"><h2 className="font-extrabold text-navy">Distance pricing</h2><p className="text-sm text-muted">Delivery fee = route distance (km) × price per km, never below the minimum. Used when the shop and the customer's hostel both have a location.</p>
        <Field label="Price per km (GH₵)"><input className="input" inputMode="decimal" value={d.rate_per_km} onChange={(e) => setD({ ...d, rate_per_km: e.target.value })} required /></Field>
        <Field label="Minimum fee (GH₵, optional)"><input className="input" inputMode="decimal" value={d.min_fee} onChange={(e) => setD({ ...d, min_fee: e.target.value })} /></Field>
        <Field label="Travel mode"><select className="input" value={d.travel_mode} onChange={(e) => setD({ ...d, travel_mode: e.target.value })}><option value="WALK">Walking</option><option value="TWO_WHEELER">Motorbike</option><option value="DRIVE">Car</option></select></Field>
        <button className="btn btn-primary w-full">Save distance pricing</button></form>
      <form onSubmit={saveFee} className="card space-y-3 p-5"><h2 className="font-extrabold text-navy">Flat fee (fallback)</h2><p className="text-sm text-muted">Used when a location is unknown. Leave unset to block checkout until locations are known.</p>
        <Field label="Flat delivery fee (GH₵)"><input className="input" inputMode="decimal" value={fee} onChange={(e) => setFee(e.target.value)} required /></Field><button className="btn btn-primary w-full">Save flat fee</button></form></div>
    <div className="card space-y-3 p-5"><div className="flex flex-wrap items-center justify-between gap-2"><h2 className="font-extrabold text-navy">Shop and hostel locations</h2>
      <div className="flex gap-2"><button className="btn btn-ghost py-2" onClick={() => geocode(false)}>Preview with Google</button>{geo && <button className="btn btn-soft py-2" onClick={() => geocode(true)}>Apply Google results</button>}</div></div>
      {geo && <div className="rounded-xl bg-slate-50 p-3 text-sm"><b>Google preview</b> (nothing saved yet):{geo.map((g) => <div key={g.type + g.id}>{g.name}: {g.found ? `${g.latitude.toFixed(5)}, ${g.longitude.toFixed(5)}` : "not found"}</div>)}</div>}
      {pins.length > 0 && <MapView pins={pins} height={260} />}
      <Table head={["Place", "Latitude", "Longitude", ""]} rows={rows.map((r) => { const k = key(r.t, r.id); const v = edit[k] || { latitude: r.latitude ?? "", longitude: r.longitude ?? "" };
        return [<span><Badge tone={r.t === "shop" ? "navy" : "mint"}>{r.t}</Badge> <b className="text-navy">{r.name}</b></span>, <input className="input w-32 py-1.5" value={v.latitude} onChange={(e) => setEdit({ ...edit, [k]: { ...v, latitude: e.target.value } })} aria-label={`${r.name} latitude`} />,
          <input className="input w-32 py-1.5" value={v.longitude} onChange={(e) => setEdit({ ...edit, [k]: { ...v, longitude: e.target.value } })} aria-label={`${r.name} longitude`} />, <button className="font-bold text-teal-dark" disabled={!edit[k]} onClick={() => saveLoc(r.t, r.id)}>Save</button>]; })} />
      <p className="text-xs text-muted">Tip: right-click a spot in Google Maps and copy the two numbers. Points marked as demo data are placeholders until you replace them.</p></div></div>;
}

function Catalog() {
  const toast = useToast(); const cats = useData(() => api<any[]>("/categories"), []); const promos = useData(() => api<any[]>("/promotions"), []); const unis = useData(() => api<any[]>("/universities"), []);
  const hostels = useData(async () => { const u = await api<any[]>("/universities"); const c = u[0]?.campuses?.[0]; return c ? api<any[]>(`/campuses/${c.id}/hostels`) : []; }, []);
  const [c, setC] = useState({ slug: "", name: "" }); const [p, setP] = useState({ title: "", body: "" }); const [h, setH] = useState(""); const [uni, setUni] = useState("");
  const go = async (fn: () => Promise<any>, ok: string, done: () => void) => { try { await fn(); toast(ok); done(); } catch (x: any) { toast(x.message, "err"); } };
  return <div className="grid gap-4 md:grid-cols-2">
    <div className="card space-y-3 p-5"><h2 className="font-extrabold text-navy">Categories</h2><div className="flex flex-wrap gap-2">{cats.data?.map((x) => <Badge key={x.id}>{x.name}</Badge>)}</div>
      <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); go(() => api("/admin/categories", { body: { slug: c.slug || c.name.toLowerCase().replace(/[^a-z0-9]+/g, "-"), name: c.name } }), "Category added", () => { setC({ slug: "", name: "" }); cats.reload(); }); }}>
        <input className="input" placeholder="New category name" value={c.name} onChange={(e) => setC({ ...c, name: e.target.value })} required /><button className="btn btn-primary">Add</button></form></div>
    <div className="card space-y-3 p-5"><h2 className="font-extrabold text-navy">Promotional banners</h2>{promos.data?.map((x) => <div key={x.id} className="rounded-xl bg-mint p-3 text-sm"><b>{x.title}</b> {x.body}</div>)}
      <form className="space-y-2" onSubmit={(e) => { e.preventDefault(); go(() => api("/admin/promotions", { body: { title: p.title, body: p.body || null } }), "Banner published", () => { setP({ title: "", body: "" }); promos.reload(); }); }}>
        <input className="input" placeholder="Banner title" value={p.title} onChange={(e) => setP({ ...p, title: e.target.value })} required /><input className="input" placeholder="Short text" value={p.body} onChange={(e) => setP({ ...p, body: e.target.value })} /><button className="btn btn-primary w-full">Publish banner</button></form></div>
    <div className="card space-y-3 p-5"><h2 className="font-extrabold text-navy">Hostels / delivery blocks</h2><div className="flex flex-wrap gap-2">{hostels.data?.map((x) => <Badge key={x.id}>{x.name}</Badge>)}</div>
      <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); go(async () => { const u = await api<any[]>("/universities"); return api("/admin/hostels", { body: { campus_id: u[0].campuses[0].id, name: h } }); }, "Hostel added", () => { setH(""); hostels.reload(); }); }}>
        <input className="input" placeholder="New hostel name" value={h} onChange={(e) => setH(e.target.value)} required /><button className="btn btn-primary">Add</button></form></div>
    <div className="card space-y-3 p-5"><h2 className="font-extrabold text-navy">University</h2>{unis.data?.map((u) => <div key={u.id} className="flex gap-2"><input className="input" defaultValue={u.name} onChange={(e) => setUni(e.target.value)} aria-label="University name" />
      <button className="btn btn-primary" onClick={() => go(() => api(`/admin/universities/${u.id}`, { method: "PUT", body: { name: uni || u.name } }), "University renamed", unis.reload)}>Rename</button></div>)}</div></div>;
}

function Support() {
  const toast = useToast(); const { data, loading, reload } = useData(() => api<any[]>("/admin/complaints"), []);
  if (loading) return <Spinner />; if (!data?.length) return <Empty title="No complaints" hint="Messages students send from Account > Need help? appear here." />;
  return <div className="space-y-3">{data.map((c) => <div key={c.id} className="card flex items-start justify-between gap-3 p-4"><div><b className="text-navy">Student #{c.user_id}</b>{c.order_id && <span className="text-sm text-muted"> · order #{c.order_id}</span>}<p className="text-sm">{c.message}</p></div>
    <div className="flex flex-col items-end gap-2"><Badge tone={c.status === "open" ? "warn" : "ok"}>{c.status}</Badge>{c.status === "open" && <button className="text-sm font-bold text-teal-dark" onClick={() => api(`/admin/complaints/${c.id}`, { body: { status: "resolved" } }).then(() => { toast("Marked resolved"); reload(); })}>Mark resolved</button>}</div></div>)}</div>;
}

function System() {
  const i = useData(() => api<any>("/admin/integrations"), []); const audit = useData(() => api<any[]>("/admin/audit?limit=40"), []);
  if (i.loading) return <Spinner />; if (i.error) return <ErrorBox message={i.error} retry={i.reload} />; const d = i.data!;
  const tone = (m: string) => (m === "live" ? "ok" : m === "unconfigured" ? "bad" : "warn");
  return <div className="space-y-6">
    {d.demo_data && <div className="rounded-2xl bg-amber-100 p-4 text-amber-900"><b>Demo data is loaded.</b> The accounts, delivery rate and map points are placeholders. Replace them before launch (checklist below).</div>}
    <div className="grid gap-4 md:grid-cols-2">
      <div className="card space-y-2 p-5"><div className="flex items-center justify-between"><h2 className="font-extrabold text-navy">Payments (Paystack)</h2><Badge tone={tone(d.payments.mode) as any}>{d.payments.mode.toUpperCase()}</Badge></div><p className="text-sm">{d.payments.note}</p>
        <p className="text-sm text-muted">Secret key set: <b>{d.payments.secret_key_set ? "yes" : "no"}</b>. Webhook URL to add in Paystack: <code className="break-all">{window.location.origin}{d.payments.webhook_url_path}</code></p></div>
      <div className="card space-y-2 p-5"><div className="flex items-center justify-between"><h2 className="font-extrabold text-navy">Maps and distance</h2><Badge tone={d.maps.google_key_set ? "ok" : "warn"}>{d.maps.google_key_set ? "GOOGLE" : "FALLBACK"}</Badge></div><p className="text-sm">{d.maps.note}</p></div>
      <div className="card space-y-2 p-5"><div className="flex items-center justify-between"><h2 className="font-extrabold text-navy">Email</h2><Badge tone="warn">{d.email.backend}</Badge></div><p className="text-sm">{d.email.note}</p></div>
      <div className="card space-y-2 p-5"><div className="flex items-center justify-between"><h2 className="font-extrabold text-navy">Push notifications</h2><Badge tone="gray">NOT SET UP</Badge></div><p className="text-sm">In-app notifications work. Phone push needs a provider (planned).</p></div></div>
    <div className="card p-5"><h2 className="mb-3 font-extrabold text-navy">Before you launch</h2><ol className="list-decimal space-y-1 pl-5 text-sm">{d.launch_checklist.map((x: string) => <li key={x}>{x}</li>)}</ol>
      <p className="mt-3 text-xs text-muted">Credentials are set as environment variables on the server (see ENVIRONMENT_VARIABLES.md). They are never entered or stored in the browser.</p></div>
    <SectionTitle>Audit log</SectionTitle><Table head={["When", "Action", "Target"]} rows={(audit.data || []).map((a) => [fmtDate(a.at), a.action, a.target || "—"])} empty="No admin actions yet." /></div>;
}
