import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { Spinner, useData, Logo } from "../ui";
import { ProductCard } from "./Explore";

const TINT: Record<string, string> = { drinks: "bg-sky-100", snacks: "bg-orange-100", breakfast: "bg-yellow-100", noodles: "bg-red-100", bread: "bg-amber-100", dairy: "bg-blue-100",
  canned: "bg-stone-200", groceries: "bg-lime-100", "personal-care": "bg-purple-100", toiletries: "bg-teal-100", household: "bg-green-100", stationery: "bg-pink-100", apparel: "bg-fuchsia-100", "frozen-chilled": "bg-cyan-100" };
const greeting = () => { const h = new Date().getHours(); return h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening"; };

export default function Home() {
  const { user } = useAuth(); const nav = useNavigate(); const [q, setQ] = useState("");
  const cats = useData(() => api<any[]>("/categories"), []);
  const pop = useData(() => api<any[]>("/products/popular?limit=8"), []);
  const shops = useData(() => api<any[]>("/shops"), []);
  const promos = useData(() => api<any[]>("/promotions"), []);
  const addrs = useData(() => api<any[]>("/auth/addresses"), []);
  const unread = useData(() => api<any[]>("/notifications"), []);
  const dest = addrs.data?.find((a) => a.is_default) || addrs.data?.[0];
  const destText = dest ? (dest.kind === "hostel" ? [dest.hostel, dest.block && `Block ${dest.block}`, dest.room && `Room ${dest.room}`].filter(Boolean).join(", ") : dest.place) : "Add a delivery spot";
  const shop = shops.data?.[0];
  const unreadN = unread.data?.filter((n) => !n.read).length || 0;
  return <div className="pb-6">
    <header className="rounded-b-[2rem] bg-navy px-5 pb-6 pt-5 text-white">
      <div className="flex items-center justify-between"><Logo light />
        <Link to="/notifications" className="relative grid h-10 w-10 place-items-center rounded-full bg-white/10" aria-label="Notifications">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M6 9a6 6 0 1112 0c0 7 3 8 3 8H3s3-1 3-8M10 21a2 2 0 004 0" /></svg>
          {unreadN > 0 && <span className="absolute -right-0.5 -top-0.5 grid h-4 min-w-4 place-items-center rounded-full bg-warn px-1 text-[10px] font-extrabold text-navy">{unreadN}</span>}</Link></div>
      <h1 className="mt-5 text-2xl font-extrabold">{greeting()}, {user?.full_name.split(" ")[0]}!</h1>
      <p className="text-white/80">What do you need today?</p>
      <Link to="/account" className="mt-3 flex items-center gap-2 rounded-2xl bg-white/10 px-3 py-2 text-sm"><span aria-hidden>📍</span><span className="truncate"><span className="text-white/70">Delivering to: </span><b>{destText}</b></span></Link>
      <form className="mt-4 flex gap-2" onSubmit={(e) => { e.preventDefault(); nav(`/explore?q=${encodeURIComponent(q)}`); }}>
        <input className="input flex-1 border-0" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search drinks, noodles, soap…" aria-label="Search products" />
        <button className="btn btn-primary px-4" aria-label="Search">Go</button></form>
    </header>
    <div className="space-y-6 px-4 pt-5">
      <section className="flex items-center gap-3 rounded-2xl bg-mint p-3 text-sm text-navy">
        <span className="grid h-10 w-10 place-items-center rounded-full bg-white text-lg">⏱</span>
        <div><b>{shop?.delivery_estimate_minutes ? `About ${shop.delivery_estimate_minutes} min` : "Fast campus delivery"}</b>
          <div className="text-muted">{shop?.delivery_estimate_minutes ? "Typical delivery time (estimate)" : "Your exact fee and time are shown at checkout"}</div></div></section>
      {promos.data?.map((p) => <section key={p.id} className="rounded-2xl bg-gradient-to-r from-teal to-navy p-4 text-white"><b>{p.title}</b><p className="text-sm text-white/85">{p.body}</p></section>)}
      <Link to="/request" className="flex items-center gap-3 rounded-2xl border-2 border-dashed border-teal bg-white p-4 shadow-card">
        <span className="grid h-12 w-12 flex-none place-items-center rounded-2xl bg-teal text-2xl text-white">＋</span>
        <div><b className="text-navy">Can't find what you need?</b><div className="text-sm text-muted">Request an item. The shop will send you a price quickly.</div></div></Link>
      <section><div className="mb-3 flex items-baseline justify-between"><h2 className="text-lg font-extrabold text-navy">Categories</h2><Link to="/explore" className="text-sm font-bold text-teal-dark">See all</Link></div>
        {cats.loading ? <Spinner /> : <div className="grid grid-cols-4 gap-2">{cats.data?.slice(0, 8).map((c) =>
          <Link key={c.id} to={`/explore?category=${c.slug}`} className="flex flex-col items-center gap-1.5 rounded-2xl bg-white p-2 text-center shadow-card">
            <span className={`grid h-12 w-12 place-items-center rounded-2xl text-lg font-extrabold text-navy ${TINT[c.slug] || "bg-mint"}`}>{c.name[0]}</span>
            <span className="text-[11px] font-bold leading-tight text-navy">{c.name}</span></Link>)}</div>}
        {cats.data && cats.data.length > 8 && <div className="mt-2 flex gap-2 overflow-x-auto pb-1">{cats.data.slice(8).map((c) => <Link key={c.id} className="chip" to={`/explore?category=${c.slug}`}>{c.name}</Link>)}</div>}</section>
      <section><div className="mb-3 flex items-baseline justify-between"><h2 className="text-lg font-extrabold text-navy">Popular with students</h2><Link to="/explore" className="text-sm font-bold text-teal-dark">See all</Link></div>
        {pop.loading ? <Spinner /> : <div className="grid grid-cols-2 gap-3">{pop.data?.map((p) => <ProductCard key={p.id} p={p} />)}</div>}</section>
      <section><h2 className="mb-3 text-lg font-extrabold text-navy">Participating shops</h2>
        {shops.data?.map((s) => <Link key={s.id} to="/explore" className="card flex items-center gap-3 p-4">
          <span className="grid h-14 w-14 place-items-center rounded-2xl bg-navy text-xl font-extrabold text-white">{s.name[0]}</span>
          <div className="min-w-0 flex-1"><b className="text-navy">{s.name}</b><div className="text-sm text-muted">{s.location}</div>
            <div className="text-xs font-bold text-teal-dark">{s.accepting_orders ? "Open for orders" : "Not taking orders right now"}</div></div><span className="text-muted">›</span></Link>)}</section>
    </div></div>;
}
