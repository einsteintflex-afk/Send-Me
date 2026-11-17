import { FormEvent, useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api, money } from "../api";
import { Cart, useCart } from "../cart";
import { Empty, Field, ProductImage, Stepper, useToast } from "../ui";

export default function CartPage() {
  const { cart, setQty, removeRequest } = useCart(); const nav = useNavigate();
  if (!cart) return <div className="p-8 text-center text-muted">Loading…</div>;
  const empty = cart.items.length === 0 && cart.requests.length === 0;
  const blocked = cart.warnings.length > 0 || cart.items.some((i) => !i.orderable) || cart.requests.some((r) => r.status === "rejected");
  return <div className="space-y-4 p-4 pb-8">
    <h1 className="text-2xl font-extrabold text-navy">Your cart</h1>
    {empty ? <Empty title="Your cart is empty" hint="Add something from the shop, or request an item that isn't listed." action={<div className="mt-2 flex gap-2"><Link to="/explore" className="btn btn-primary">Browse shop</Link><Link to="/request" className="btn btn-soft">Request item</Link></div>} /> : <>
      {cart.shop_name && <p className="text-sm text-muted">From <b className="text-navy">{cart.shop_name}</b></p>}
      {cart.warnings.map((w) => <p key={w} role="alert" className="rounded-xl bg-amber-50 p-3 text-sm font-semibold text-amber-900">{w}</p>)}
      <div className="space-y-3">{cart.items.map((i) => <div key={i.id} className="card flex gap-3 p-3">
        <ProductImage name={i.name} category="" url={i.image_url} className="h-16 w-16 flex-none rounded-2xl" />
        <div className="min-w-0 flex-1"><div className="truncate font-bold text-navy">{i.name}</div>{i.variant && <div className="text-xs text-muted">{i.variant}</div>}
          <div className="text-sm text-muted tabular-nums">{money(i.unit_price)} each</div>
          <div className="mt-2 flex items-center justify-between"><Stepper value={i.quantity} onChange={(n) => setQty(i.id, n)} /><b className="tabular-nums text-navy">{money(i.line_total)}</b></div></div></div>)}</div>
      {cart.requests.length > 0 && <section className="space-y-3"><h2 className="font-extrabold text-navy">Requested items <span className="text-xs font-semibold text-amber-700">(not in catalogue)</span></h2>
        {cart.requests.map((r) => <div key={r.id} className="rounded-3xl border-2 border-dashed border-warn bg-amber-50 p-3">
          <div className="flex items-start justify-between gap-2"><div><b className="text-navy">{r.quantity} × {r.name}</b>{r.brand && <span className="text-sm text-muted"> · {r.brand}</span>}
            {r.description && <p className="text-sm text-navy/80">{r.description}</p>}</div>
            <button onClick={() => removeRequest(r.id)} className="text-sm font-bold text-bad">Remove</button></div>
          <p className={`mt-2 text-sm font-semibold ${r.status === "priced" ? "text-ok" : r.status === "rejected" ? "text-bad" : "text-amber-800"}`}>
            {r.status === "priced" ? `Shop price: ${money(r.unit_price)} each` : r.message}</p>
          {r.shop_note && <p className="text-sm text-muted">Shop note: {r.shop_note}</p>}</div>)}</section>}
      <Link to="/request" className="btn btn-ghost w-full">＋ Request an item that isn't listed</Link>
      <div className="card space-y-2 p-4">
        <Row k="Subtotal" v={money(cart.subtotal)} />
        <Row k="Delivery fee" v={cart.delivery_needs_destination ? "Calculated at checkout" : cart.delivery_fee != null ? money(cart.delivery_fee) : "Not set"} />
        {cart.discount > 0 && <Row k="Discount" v={"− " + money(cart.discount)} />}
        <div className="flex justify-between border-t border-dashed border-slate-300 pt-2 text-lg font-extrabold text-navy"><span>Total payable</span><span className="tabular-nums">{cart.total != null ? money(cart.total) : "At checkout"}</span></div>
        {cart.pending_confirmation && <p className="text-xs text-amber-800">Requested items are charged only after the shop confirms a price and you approve it.</p>}</div>
      <button className="btn btn-primary w-full" disabled={blocked} onClick={() => nav("/checkout")}>Continue to checkout</button></>}
  </div>;
}
const Row = ({ k, v }: { k: string; v: string }) => <div className="flex justify-between text-navy"><span className="text-muted">{k}</span><span className="font-semibold tabular-nums">{v}</span></div>;

export function RequestItem() {
  const [sp] = useSearchParams(); const nav = useNavigate(); const toast = useToast(); const { setCart } = useCart();
  const [shops, setShops] = useState<any[]>([]);
  const [f, setF] = useState({ name: sp.get("name") || "", description: "", brand: "", quantity: 1 });
  const [img, setImg] = useState<string | null>(null); const [busy, setBusy] = useState(false); const [err, setErr] = useState("");
  useEffect(() => { api("/shops").then(setShops); }, []);
  const upload = async (file?: File) => { if (!file) return; const fd = new FormData(); fd.append("file", file);
    try { setImg((await api("/cart/requests/image", { form: fd })).image_url); } catch (e: any) { toast(e.message, "err"); } };
  const submit = async (e: FormEvent) => { e.preventDefault(); setErr(""); setBusy(true);
    try { setCart(await api<Cart>("/cart/requests", { body: { shop_id: shops[0].id, ...f, brand: f.brand || null, description: f.description || null, image_url: img } }));
      toast("Request sent. We'll notify you with the price."); nav("/cart"); } catch (x: any) { setErr(x.message); } finally { setBusy(false); } };
  return <div className="space-y-4 p-4 pb-8">
    <div className="flex items-center gap-2"><button onClick={() => nav(-1)} className="grid h-10 w-10 place-items-center rounded-full bg-white text-xl shadow-card" aria-label="Back">‹</button><h1 className="text-xl font-extrabold text-navy">Request an item</h1></div>
    <div className="rounded-2xl bg-mint p-4 text-sm text-navy"><b>Can't find what you need?</b> Type it below. The shop and Send Me admin are alerted straight away and will send you a price. You only pay once you approve it.</div>
    <form onSubmit={submit} className="space-y-4">
      <Field label="What do you want to buy?"><input className="input" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} placeholder="e.g. A4 notebook, Dettol soap" required minLength={2} /></Field>
      <Field label="Describe it (optional)"><textarea className="input" rows={3} value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} placeholder="Size, colour, flavour…" /></Field>
      <div className="grid grid-cols-2 gap-3"><Field label="Preferred brand"><input className="input" value={f.brand} onChange={(e) => setF({ ...f, brand: e.target.value })} /></Field>
        <div><span className="label">Quantity</span><Stepper value={f.quantity} min={1} onChange={(n) => setF({ ...f, quantity: Math.min(50, n) })} /></div></div>
      <Field label="Reference photo (optional)"><input type="file" accept="image/jpeg,image/png,image/webp" onChange={(e) => upload(e.target.files?.[0])} className="block w-full text-sm" /></Field>
      {img && <p className="text-sm font-semibold text-ok">Photo attached ✓</p>}
      {err && <p role="alert" className="rounded-xl bg-red-50 p-3 text-sm font-semibold text-bad">{err}</p>}
      <button className="btn btn-primary w-full" disabled={busy || !shops.length}>{busy ? "Sending…" : "Send request"}</button></form></div>;
}
