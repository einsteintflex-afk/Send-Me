import { createContext, ReactNode, useCallback, useContext, useEffect, useState } from "react";
import { api } from "./api";
import { useAuth } from "./auth";
import { useToast } from "./ui";

export type CartLine = { id: number; product_id: number; name: string; variant: string | null; variant_id: number | null; image_url: string | null;
  unit_price: number | null; quantity: number; line_total: number | null; orderable: boolean };
export type CartReq = { id: number; name: string; description: string | null; brand: string | null; quantity: number; image_url: string | null;
  status: string; unit_price: number | null; shop_note: string | null; message: string };
export type Cart = { shop_id: number | null; shop_name: string | null; items: CartLine[]; requests: CartReq[]; subtotal: number; delivery_fee: number | null;
  discount: number; total: number | null; warnings: string[]; fee_configured: boolean; delivery_needs_destination: boolean;
  delivery_distance_km: number | null; delivery_method: string | null; pending_confirmation: boolean };

type Ctx = { cart: Cart | null; count: number; refresh: () => Promise<void>; add: (productId: number, qty?: number, variantId?: number | null) => Promise<boolean>;
  setQty: (lineId: number, qty: number) => Promise<void>; removeRequest: (id: number) => Promise<void>; setCart: (c: Cart) => void };
const C = createContext<Ctx>(null as any);
export const useCart = () => useContext(C);

export function CartProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const toast = useToast();
  const [cart, setCart] = useState<Cart | null>(null);
  const refresh = useCallback(async () => { if (user?.role !== "student") { setCart(null); return; } try { setCart(await api<Cart>("/cart")); } catch { /* ignore */ } }, [user]);
  useEffect(() => { refresh(); }, [refresh]);
  const add: Ctx["add"] = async (productId, qty = 1, variantId = null) => {
    try { setCart(await api<Cart>("/cart/items", { body: { product_id: productId, quantity: qty, variant_id: variantId } })); toast("Added to cart"); return true; }
    catch (e: any) { toast(e.message, "err"); return false; }
  };
  const setQty: Ctx["setQty"] = async (lineId, qty) => {
    try { setCart(await api<Cart>(`/cart/items/${lineId}`, { method: "PATCH", body: { quantity: qty } })); } catch (e: any) { toast(e.message, "err"); }
  };
  const removeRequest: Ctx["removeRequest"] = async (id) => { try { setCart(await api<Cart>(`/cart/requests/${id}`, { method: "DELETE" })); toast("Request removed"); } catch (e: any) { toast(e.message, "err"); } };
  const count = (cart?.items.reduce((a, i) => a + i.quantity, 0) || 0) + (cart?.requests.length || 0);
  return <C.Provider value={{ cart, count, refresh, add, setQty, removeRequest, setCart }}>{children}</C.Provider>;
}
