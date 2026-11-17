import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, localPhone, money } from "../api";
import { useCart } from "../cart";
import { Empty, ErrorBox, ProductImage, Spinner, Stepper, useData } from "../ui";

export type Product = { id: number; name: string; price: number | null; category: string; category_name: string; image_url: string | null; availability: string;
  orderable: boolean; has_variants: boolean; shop_id: number; price_listed: boolean };

export function ProductCard({ p }: { p: Product }) {
  const { cart, add, setQty } = useCart();
  const line = cart?.items.find((i) => i.product_id === p.id && !p.has_variants);
  return <div className="card overflow-hidden">
    <Link to={`/product/${p.id}`} aria-label={`${p.name} details`}>
      <ProductImage name={p.name} category={p.category} url={p.image_url} className="aspect-[4/3] w-full" />
      <div className="space-y-1 p-3"><div className="line-clamp-2 min-h-[2.5rem] text-sm font-bold leading-tight text-navy">{p.name}</div>
        <div className="flex items-center justify-between"><span className="font-extrabold tabular-nums text-teal-dark">{p.price != null ? money(p.price) : p.has_variants ? "See options" : "Price to come"}</span></div>
        <div className={`text-[11px] font-bold ${p.orderable ? "text-ok" : "text-bad"}`}>{p.orderable ? "Available" : p.price_listed ? "Unavailable" : "Not orderable yet"}</div></div></Link>
    <div className="px-3 pb-3">{!p.orderable ? <Link to={`/request?name=${encodeURIComponent(p.name)}`} className="btn btn-soft w-full py-2 text-sm">Request it</Link>
      : p.has_variants ? <Link to={`/product/${p.id}`} className="btn btn-soft w-full py-2 text-sm">Choose option</Link>
      : line ? <div className="flex justify-center"><Stepper value={line.quantity} onChange={(n) => setQty(line.id, n)} /></div>
      : <button className="btn btn-soft w-full py-2 text-sm" onClick={() => add(p.id)}>Add to cart</button>}</div></div>;
}

const RECENT = "sendme.recent";
const loadRecent = (): string[] => { try { return JSON.parse(localStorage.getItem(RECENT) || "[]"); } catch { return []; } };

export default function Explore() {
  const [sp, setSp] = useSearchParams();
  const q = sp.get("q") || ""; const category = sp.get("category") || "";
  const [text, setText] = useState(q); const [onlyAvail, setOnly] = useState(false);
  const [sugg, setSugg] = useState<string[]>([]); const [recent, setRecent] = useState<string[]>(loadRecent());
  const [focus, setFocus] = useState(false); const t = useRef<number>();
  const cats = useData(() => api<any[]>("/categories"), []);
  const shops = useData(() => api<any[]>("/shops"), []);
  const popular = useData(() => api<string[]>("/search/popular"), []);
  const res = useData(() => api<{ total: number; items: Product[] }>(`/products?limit=100&q=${encodeURIComponent(q)}&category=${category}${onlyAvail ? "&availability=available" : ""}`), [q, category, onlyAvail]);
  const shop = shops.data?.[0];
  useEffect(() => setText(q), [q]);
  const onType = (v: string) => { setText(v); clearTimeout(t.current); if (!v.trim()) { setSugg([]); return; } t.current = window.setTimeout(() => api<string[]>(`/search/suggestions?q=${encodeURIComponent(v)}`).then(setSugg).catch(() => {}), 200); };
  const go = (v: string) => { const n = new URLSearchParams(sp); v ? n.set("q", v) : n.delete("q"); setSp(n); setFocus(false);
    if (v.trim()) { const r = [v, ...recent.filter((x) => x !== v)].slice(0, 6); setRecent(r); try { localStorage.setItem(RECENT, JSON.stringify(r)); } catch { /* ignore */ } } };
  const setCat = (c: string) => { const n = new URLSearchParams(sp); c ? n.set("category", c) : n.delete("category"); setSp(n); };
  return <div className="pb-6">
    <div className="sticky top-0 z-20 bg-paper px-4 pb-2 pt-4">
      <form onSubmit={(e) => { e.preventDefault(); go(text); }} className="relative">
        <input className="input pr-24" value={text} onChange={(e) => onType(e.target.value)} onFocus={() => setFocus(true)} placeholder="Search products, categories…" aria-label="Search" />
        <div className="absolute right-2 top-1.5 flex gap-1">{text && <button type="button" className="px-2 text-xl text-muted" aria-label="Clear" onClick={() => { setText(""); go(""); }}>×</button>}<button className="btn btn-primary px-3 py-1.5 text-sm">Search</button></div>
        {focus && (sugg.length > 0 || (!text && (recent.length > 0 || (popular.data?.length || 0) > 0))) &&
          <div className="absolute left-0 right-0 top-14 z-30 max-h-72 overflow-y-auto rounded-2xl bg-white p-2 shadow-card">
            {text ? sugg.map((s) => <button type="button" key={s} className="block w-full rounded-xl px-3 py-2 text-left hover:bg-mint" onMouseDown={() => go(s)}>{s}</button>) : <>
              {recent.length > 0 && <><div className="px-3 pt-1 text-xs font-bold uppercase text-muted">Recent</div>{recent.map((s) => <button type="button" key={s} className="block w-full rounded-xl px-3 py-2 text-left hover:bg-mint" onMouseDown={() => go(s)}>{s}</button>)}</>}
              {(popular.data?.length || 0) > 0 && <><div className="px-3 pt-2 text-xs font-bold uppercase text-muted">Popular searches</div>{popular.data!.map((s) => <button type="button" key={s} className="block w-full rounded-xl px-3 py-2 text-left hover:bg-mint" onMouseDown={() => go(s)}>{s}</button>)}</>}</>}
          </div>}</form>
      <div className="-mx-4 mt-3 flex gap-2 overflow-x-auto px-4 pb-1">
        <button className={`chip ${!category ? "chip-on" : ""}`} onClick={() => setCat("")}>All</button>
        {cats.data?.map((c) => <button key={c.id} className={`chip ${category === c.slug ? "chip-on" : ""}`} onClick={() => setCat(category === c.slug ? "" : c.slug)}>{c.name}</button>)}</div></div>
    <div className="space-y-4 px-4">
      {shop && <section className="card p-4"><div className="flex items-start justify-between gap-2"><div><h1 className="text-lg font-extrabold text-navy">{shop.name}</h1><p className="text-sm text-muted">📍 {shop.location}</p></div>
        <span className={`rounded-full px-2.5 py-1 text-xs font-bold ${shop.accepting_orders ? "bg-green-100 text-ok" : "bg-red-100 text-bad"}`}>{shop.accepting_orders ? "Open" : "Closed"}</span></div>
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm text-navy">{shop.phones.map((p: string) => <a key={p} className="font-semibold text-teal-dark" href={`tel:${p}`}>📞 {localPhone(p)}</a>)}
          <span>⏱ {shop.delivery_estimate_minutes ? `~${shop.delivery_estimate_minutes} min` : "Time shown at checkout"}</span></div>
        {Object.keys(shop.opening_hours || {}).length > 0 && <p className="mt-1 text-xs text-muted">Hours: {Object.entries(shop.opening_hours).map(([d, h]) => `${d} ${h}`).join(" · ")}</p>}</section>}
      <div className="flex items-center justify-between"><p className="text-sm text-muted" aria-live="polite">{res.data ? `${res.data.total} item${res.data.total === 1 ? "" : "s"}` : ""}</p>
        <label className="flex items-center gap-2 text-sm font-semibold text-navy"><input type="checkbox" checked={onlyAvail} onChange={(e) => setOnly(e.target.checked)} className="h-4 w-4 accent-teal" />Available only</label></div>
      {res.loading ? <Spinner label="Finding products" /> : res.error ? <ErrorBox message={res.error} retry={res.reload} /> :
        res.data!.items.length === 0 ? <Empty title={`No match${q ? ` for “${q}”` : ""}`} hint="Check the spelling, try a simpler word, or ask the shop for it." action={<Link to={`/request?name=${encodeURIComponent(q)}`} className="btn btn-primary mt-2">Request this item</Link>} /> :
          <><div className="grid grid-cols-2 gap-3">{res.data!.items.map((p) => <ProductCard key={p.id} p={p} />)}</div>
            <Link to={`/request?name=${encodeURIComponent(q)}`} className="block rounded-2xl border-2 border-dashed border-teal bg-white p-4 text-center"><b className="text-navy">Can't find it?</b><div className="text-sm text-muted">Request an item that isn't listed</div></Link></>}
    </div></div>;
}
