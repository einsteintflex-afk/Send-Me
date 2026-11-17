import { FormEvent, useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { homeFor, useAuth } from "../auth";
import { Field, Logo, Spinner, useToast } from "../ui";

export function Welcome() {
  const { config } = useAuth();
  return <div className="mx-auto flex min-h-full max-w-md flex-col bg-navy text-white">
    <div className="flex flex-1 flex-col justify-center gap-6 px-6 py-12">
      <Logo light />
      <h1 className="text-4xl font-extrabold leading-tight">Your Campus.<br />Your Essentials.<br /><span className="text-teal">Delivered.</span></h1>
      <p className="text-white/80">Order drinks, snacks, toiletries and more from the shop near you. We bring it to your hostel.</p>
      <ul className="space-y-2 text-sm text-white/90">
        <li>✓ Pay with Mobile Money or card</li><li>✓ Track your rider live on the map</li><li>✓ Can't find an item? Just type it and we'll quote you</li></ul>
    </div>
    <div className="space-y-3 px-6 pb-10">
      <Link to="/register" className="btn btn-primary w-full">Create account</Link>
      <Link to="/login" className="btn w-full bg-white/10 text-white hover:bg-white/20">I already have an account</Link>
      {config?.demo && <p className="pt-2 text-center text-xs text-amber-300">Demo mode: placeholder data</p>}
    </div></div>;
}

function Shell({ title, sub, children }: { title: string; sub?: string; children: React.ReactNode }) {
  return <div className="mx-auto min-h-full max-w-md px-5 py-8"><Link to="/welcome" className="mb-6 block"><Logo /></Link>
    <h1 className="text-2xl font-extrabold text-navy">{title}</h1>{sub && <p className="mb-5 mt-1 text-muted">{sub}</p>}{children}</div>;
}

export function Login() {
  const { login, config } = useAuth();
  const nav = useNavigate();
  const [id, setId] = useState(""); const [pw, setPw] = useState(""); const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);
  const submit = async (e: FormEvent) => { e.preventDefault(); setErr(""); setBusy(true);
    try { const u = await login(id.trim(), pw); nav(homeFor(u.role), { replace: true }); } catch (x: any) { setErr(x.message); } finally { setBusy(false); } };
  return <Shell title="Welcome back" sub="Sign in with your phone number or email.">
    <form onSubmit={submit} className="space-y-4">
      <Field label="Phone or email"><input className="input" value={id} onChange={(e) => setId(e.target.value)} autoComplete="username" placeholder="024 123 4567" required /></Field>
      <Field label="Password"><input className="input" type="password" value={pw} onChange={(e) => setPw(e.target.value)} autoComplete="current-password" required /></Field>
      {err && <p role="alert" className="rounded-xl bg-red-50 p-3 text-sm font-semibold text-bad">{err}</p>}
      <button className="btn btn-primary w-full" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
      <div className="flex justify-between text-sm font-semibold text-teal-dark"><Link to="/forgot">Forgot password?</Link><Link to="/register">Create account</Link></div>
    </form>
    {config?.demo && <div className="mt-8 rounded-2xl bg-amber-50 p-4 text-sm text-amber-900"><b>Demo accounts</b> (development only, password <code>demo12345</code>):
      <ul className="mt-1 list-disc pl-5"><li>Student 0200000003</li><li>Shop manager 0200000002</li><li>Rider 0200000004</li><li>Administrator 0200000001</li></ul></div>}
  </Shell>;
}

export function Register() {
  const { register } = useAuth(); const nav = useNavigate(); const toast = useToast();
  const [unis, setUnis] = useState<any[]>([]); const [hostels, setHostels] = useState<any[]>([]);
  const [f, setF] = useState({ full_name: "", phone: "", email: "", password: "", university_id: 0, hostel: "", block: "", room: "" });
  const [other, setOther] = useState(false); const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);
  useEffect(() => { api("/universities").then((u) => { setUnis(u); if (u[0]) setF((x) => ({ ...x, university_id: u[0].id })); }); }, []);
  useEffect(() => { const u = unis.find((x) => x.id === f.university_id); const c = u?.campuses?.[0]; if (c) api(`/campuses/${c.id}/hostels`).then(setHostels); }, [f.university_id, unis]);
  const set = (k: string) => (e: any) => setF({ ...f, [k]: e.target.value });
  const submit = async (e: FormEvent) => { e.preventDefault(); setErr(""); setBusy(true);
    try { await register({ ...f, block: f.block || null }); toast("Account created. Welcome to Send Me!"); nav("/", { replace: true }); } catch (x: any) { setErr(x.message); } finally { setBusy(false); } };
  return <Shell title="Create your account" sub="Takes a minute. We use this to deliver to your room.">
    <form onSubmit={submit} className="space-y-4">
      <Field label="Full name"><input className="input" value={f.full_name} onChange={set("full_name")} autoComplete="name" required minLength={2} /></Field>
      <Field label="Phone number" hint="Ghana number, e.g. 024 123 4567"><input className="input" value={f.phone} onChange={set("phone")} inputMode="tel" autoComplete="tel" required /></Field>
      <Field label="Email"><input className="input" type="email" value={f.email} onChange={set("email")} autoComplete="email" required /></Field>
      <Field label="Password" hint="At least 8 characters"><input className="input" type="password" value={f.password} onChange={set("password")} autoComplete="new-password" required minLength={8} /></Field>
      <Field label="University"><select className="input" value={f.university_id} onChange={(e) => setF({ ...f, university_id: +e.target.value })}>{unis.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}</select></Field>
      <Field label="Hostel / residence">
        {hostels.length > 0 && !other ? <select className="input" value={f.hostel} onChange={(e) => e.target.value === "__other" ? (setOther(true), setF({ ...f, hostel: "" })) : set("hostel")(e)} required>
          <option value="">Choose your hostel</option>{hostels.map((h) => <option key={h.id} value={h.name}>{h.name}</option>)}<option value="__other">Other (type it)</option></select>
          : <input className="input" value={f.hostel} onChange={set("hostel")} placeholder="Hostel name" required />}</Field>
      <div className="grid grid-cols-2 gap-3"><Field label="Block (optional)"><input className="input" value={f.block} onChange={set("block")} /></Field>
        <Field label="Room number"><input className="input" value={f.room} onChange={set("room")} required /></Field></div>
      {err && <p role="alert" className="rounded-xl bg-red-50 p-3 text-sm font-semibold text-bad">{err}</p>}
      <button className="btn btn-primary w-full" disabled={busy}>{busy ? "Creating…" : "Create account"}</button>
      <p className="text-center text-sm text-muted">Already registered? <Link className="font-bold text-teal-dark" to="/login">Sign in</Link></p>
    </form></Shell>;
}

export function Forgot() {
  const [email, setEmail] = useState(""); const [done, setDone] = useState(""); const [err, setErr] = useState("");
  const submit = async (e: FormEvent) => { e.preventDefault(); setErr(""); try { const r = await api("/auth/forgot-password", { body: { email } }); setDone(r.message); } catch (x: any) { setErr(x.message); } };
  return <Shell title="Reset your password" sub="Enter your email and we'll send a reset link. Riders without email: ask the Send Me admin to reset it for you.">
    {done ? <p className="rounded-2xl bg-mint p-4 font-semibold text-teal-dark">{done}</p> :
      <form onSubmit={submit} className="space-y-4"><Field label="Email"><input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required /></Field>
        {err && <p className="text-sm font-semibold text-bad">{err}</p>}<button className="btn btn-primary w-full">Send reset link</button></form>}
    <Link to="/login" className="mt-6 block text-center text-sm font-bold text-teal-dark">Back to sign in</Link></Shell>;
}

export function ResetPassword() {
  const [sp] = useSearchParams(); const nav = useNavigate(); const toast = useToast();
  const [pw, setPw] = useState(""); const [err, setErr] = useState("");
  const submit = async (e: FormEvent) => { e.preventDefault(); setErr(""); try { await api("/auth/reset-password", { body: { token: sp.get("token") || "", password: pw } }); toast("Password changed. Sign in."); nav("/login"); } catch (x: any) { setErr(x.message); } };
  return <Shell title="Choose a new password"><form onSubmit={submit} className="space-y-4">
    <Field label="New password" hint="At least 8 characters"><input className="input" type="password" value={pw} onChange={(e) => setPw(e.target.value)} minLength={8} required /></Field>
    {err && <p className="text-sm font-semibold text-bad">{err}</p>}<button className="btn btn-primary w-full">Save password</button></form></Shell>;
}

export function VerifyEmail() {
  const [sp] = useSearchParams(); const [state, setState] = useState<"busy" | "ok" | string>("busy");
  useEffect(() => { api("/auth/verify-email", { body: { token: sp.get("token") || "" } }).then(() => setState("ok")).catch((e) => setState(e.message)); }, [sp]);
  return <Shell title="Email verification">{state === "busy" ? <Spinner label="Verifying" /> : state === "ok" ?
    <p className="rounded-2xl bg-mint p-4 font-semibold text-teal-dark">Your email is verified.</p> : <p className="rounded-2xl bg-red-50 p-4 font-semibold text-bad">{state}</p>}
    <Link to="/" className="btn btn-primary mt-6 w-full">Continue</Link></Shell>;
}
