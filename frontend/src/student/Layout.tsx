import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth";
import { useCart } from "../cart";
import { DemoBanner } from "../ui";

const I = {
  home: "M3 11l9-8 9 8v10a1 1 0 01-1 1h-5v-7H9v7H4a1 1 0 01-1-1z",
  explore: "M11 4a7 7 0 100 14 7 7 0 000-14zm9 16l-4-4",
  orders: "M6 3h12v18l-3-2-3 2-3-2-3 2zM9 8h6M9 12h6",
  cart: "M3 4h2l2 12h11l2-8H6M9 20a1 1 0 100 .01M17 20a1 1 0 100 .01",
  account: "M12 12a4 4 0 100-8 4 4 0 000 8zm-8 9a8 8 0 0116 0",
};
const Icon = ({ d }: { d: string }) => <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d={d} /></svg>;

export default function StudentLayout() {
  const { count } = useCart(); const { config } = useAuth();
  const item = (to: string, label: string, d: string, end = false) => (
    <NavLink to={to} end={end} className={({ isActive }) => `flex flex-1 flex-col items-center gap-0.5 py-2 text-[11px] font-bold ${isActive ? "text-teal" : "text-muted"}`}><Icon d={d} />{label}</NavLink>);
  return <div className="mx-auto flex h-full max-w-md flex-col bg-paper shadow-2xl">
    <DemoBanner show={config?.demo} />
    <main className="flex-1 overflow-y-auto"><Outlet /></main>
    <nav className="relative z-10 flex border-t border-slate-200 bg-white" style={{ paddingBottom: "env(safe-area-inset-bottom)" }} aria-label="Main">
      {item("/", "Home", I.home, true)}{item("/explore", "Explore", I.explore)}{item("/orders", "Orders", I.orders)}
      <NavLink to="/cart" className={({ isActive }) => `relative flex flex-1 flex-col items-center gap-0.5 py-2 text-[11px] font-bold ${isActive ? "text-teal" : "text-muted"}`}>
        <span className={`-mt-6 grid h-12 w-12 place-items-center rounded-full bg-teal text-white shadow-card ring-4 ring-white`}><Icon d={I.cart} /></span>Cart
        {count > 0 && <span className="absolute right-4 top-[-18px] grid h-5 min-w-5 place-items-center rounded-full bg-warn px-1 text-[11px] font-extrabold text-navy">{count}</span>}</NavLink>
      {item("/account", "Account", I.account)}
    </nav></div>;
}
