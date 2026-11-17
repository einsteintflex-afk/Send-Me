import { ReactNode, useEffect } from "react";
import { Navigate, Outlet, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { homeFor, useAuth } from "./auth";
import { CartProvider } from "./cart";
import { Spinner } from "./ui";
import { Forgot, Login, Register, ResetPassword, VerifyEmail, Welcome } from "./student/Auth";
import StudentLayout from "./student/Layout";
import Home from "./student/Home";
import Explore from "./student/Explore";
import ProductPage from "./student/Product";
import CartPage, { RequestItem } from "./student/Cart";
import Checkout from "./student/Checkout";
import { MockPay, OrderDetail, OrdersList } from "./student/Orders";
import { Account, Notifications } from "./student/Account";
import ShopApp from "./shop/ShopApp";
import RiderApp from "./rider/RiderApp";
import AdminApp from "./admin/AdminApp";

function Guard({ roles, children }: { roles: string[]; children: ReactNode }) {
  const { user, loading } = useAuth(); const loc = useLocation();
  if (loading) return <Spinner />;
  if (!user) return <Navigate to="/welcome" replace state={{ from: loc.pathname }} />;
  if (!roles.includes(user.role)) return <Navigate to={homeFor(user.role)} replace />;
  return <>{children}</>;
}

/** Paystack sends the browser back to /?order=ID&reference=REF. Turn that into an in-app route. */
function PayReturn() {
  const nav = useNavigate();
  useEffect(() => {
    const p = new URLSearchParams(window.location.search); const order = p.get("order"); const ref = p.get("reference") || p.get("trxref");
    if (order) { window.history.replaceState({}, "", window.location.pathname); nav(`/orders/${order}${ref ? `?verify=${encodeURIComponent(ref)}` : ""}`, { replace: true }); }
  }, [nav]);
  return null;
}

export default function App() {
  return <><PayReturn /><Routes>
    <Route path="/welcome" element={<Welcome />} /><Route path="/login" element={<Login />} /><Route path="/register" element={<Register />} />
    <Route path="/forgot" element={<Forgot />} /><Route path="/reset" element={<ResetPassword />} /><Route path="/verify" element={<VerifyEmail />} />
    <Route element={<Guard roles={["student"]}><CartProvider><StudentLayout /></CartProvider></Guard>}>
      <Route index element={<Home />} /><Route path="explore" element={<Explore />} /><Route path="product/:id" element={<ProductPage />} />
      <Route path="cart" element={<CartPage />} /><Route path="request" element={<RequestItem />} /><Route path="checkout" element={<Checkout />} />
      <Route path="pay/mock" element={<MockPay />} /><Route path="orders" element={<OrdersList />} /><Route path="orders/:id" element={<OrderDetail />} />
      <Route path="account" element={<Account />} /><Route path="notifications" element={<Notifications />} /></Route>
    <Route path="/shop/*" element={<Guard roles={["shop_admin", "shop_staff", "super_admin"]}><ShopApp /></Guard>} />
    <Route path="/rider/*" element={<Guard roles={["rider"]}><RiderApp /></Guard>} />
    <Route path="/admin/*" element={<Guard roles={["super_admin"]}><AdminApp /></Guard>} />
    <Route path="*" element={<Navigate to="/" replace />} />
  </Routes></>;
}
