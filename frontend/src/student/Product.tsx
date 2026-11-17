import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, money } from "../api";
import { useCart } from "../cart";
import { ErrorBox, ProductImage, Spinner, Stepper, useData } from "../ui";

export default function ProductPage() {
  const { id } = useParams(); const nav = useNavigate(); const { add } = useCart();
  const { data: p, loading, error, reload } = useData(() => api<any>(`/products/${id}`), [id]);
  const [qty, setQty] = useState(1); const [variant, setVariant] = useState<number | null>(null);
  useEffect(() => { if (p?.variants?.length) setVariant((p.variants.find((v: any) => v.orderable) || p.variants[0]).id); }, [p]);
  if (loading) return <Spinner />; if (error || !p) return <ErrorBox message={error || "Product not found."} retry={reload} />;
  const v = p.variants?.find((x: any) => x.id === variant);
  const price = v ? v.price : p.price; const orderable = v ? v.orderable : p.orderable;
  return <div>
    <div className="relative"><ProductImage name={p.name} category={p.category} url={p.image_url} className="aspect-square w-full" />
      <button onClick={() => nav(-1)} className="absolute left-4 top-4 grid h-10 w-10 place-items-center rounded-full bg-white text-xl shadow-card" aria-label="Back">‹</button></div>
    <div className="-mt-6 space-y-4 rounded-t-[2rem] bg-paper px-5 pt-6">
      <div><div className="text-xs font-bold uppercase tracking-wide text-teal-dark">{p.category_name}</div><h1 className="text-2xl font-extrabold text-navy">{p.name}</h1>
        <div className="mt-1 text-sm text-muted">Sold by {p.shop_name}</div></div>
      <div className="flex items-center justify-between"><div className="text-3xl font-extrabold tabular-nums text-navy">{price != null ? money(price) : "Price to come"}</div>
        <span className={`rounded-full px-3 py-1 text-sm font-bold ${orderable ? "bg-green-100 text-ok" : "bg-red-100 text-bad"}`}>{orderable ? "Available" : price == null ? "Not orderable yet" : "Unavailable"}</span></div>
      {p.description && <p className="text-navy/80">{p.description}</p>}
      {p.variants?.length > 0 && <div><span className="label">Choose an option</span><div className="grid gap-2">{p.variants.map((x: any) =>
        <button key={x.id} disabled={!x.orderable} onClick={() => setVariant(x.id)} className={`flex items-center justify-between rounded-2xl border-2 px-4 py-3 text-left font-semibold disabled:opacity-40 ${variant === x.id ? "border-teal bg-mint" : "border-slate-200 bg-white"}`}>
          <span>{x.name}</span><span className="tabular-nums">{money(x.price)}</span></button>)}</div></div>}
      {!orderable && <div className="rounded-2xl bg-amber-50 p-4 text-sm text-amber-900">{price == null ? "The shop hasn't listed a price for this yet, so it can't be ordered directly." : "This item is out of stock right now."} You can ask the shop for it.
        <Link to={`/request?name=${encodeURIComponent(p.name)}`} className="btn btn-primary mt-3 w-full">Request this item</Link></div>}
    </div>
    {orderable && <div className="sticky bottom-0 z-30 mt-6 flex items-center gap-3 border-t border-slate-200 bg-white p-4">
      <Stepper value={qty} onChange={setQty} min={1} />
      <button className="btn btn-primary flex-1" onClick={async () => { if (await add(p.id, qty, v?.id ?? null)) nav("/cart"); }}>Add · {money((price || 0) * qty)}</button></div>}
  </div>;
}
