const { chromium } = require("playwright");
const BASE = "http://localhost:8000";
const call = async (m, p, t, b) => { const r = await fetch(BASE + p, { method: m, headers: { "Content-Type": "application/json", ...(t ? { Authorization: "Bearer " + t } : {}) }, body: b ? JSON.stringify(b) : undefined }); const j = await r.json().catch(() => ({})); if (!r.ok) throw new Error(p + JSON.stringify(j)); return j; };
const tok = async (id) => (await call("POST", "/auth/login", null, { identifier: id, password: "demo12345" })).access_token;
(async () => {
  const st = await tok("0200000003"); const bread = (await call("GET", "/products?q=bread")).items.find((p) => p.name === "Bread");
  const b = await chromium.launch(); const p = await (await b.newContext({ viewport: { width: 1100, height: 800 } })).newPage();
  await p.goto(BASE + "/#/login"); await p.getByLabel("Phone or email").fill("0200000002"); await p.getByLabel("Password").fill("demo12345"); await p.getByRole("button", { name: "Sign in" }).click(); await p.getByText("Shop dashboard").first().waitFor();
  for (let i = 0; i < 8; i++) {
    await call("POST", "/cart/items", st, { product_id: bread.id }); const a = (await call("GET", "/auth/addresses", st))[0]; const o = await call("POST", "/checkout", st, { address_id: a.id });
    const pay = await call("POST", `/orders/${o.id}/pay`, st, {}); await call("POST", `/dev/mock-pay/${pay.reference}`, st, { outcome: "success" }); await call("POST", `/payments/verify/${pay.reference}`, st, {});
    await p.goto(BASE + "/#/shop/orders"); await p.reload(); await p.getByText("Needs your response").first().click(); await p.getByRole("button", { name: "Accept order" }).click(); await p.getByRole("button", { name: "Start preparing" }).click();
    await p.getByLabel("Choose rider").selectOption({ label: "Demo Rider (020 000 0004)" });
    const dis = async () => p.getByRole("button", { name: "Assign", exact: true }).isDisabled();
    await p.waitForTimeout(300); const d1 = await dis(); await p.waitForTimeout(2000); const d2 = await dis();
    console.log(i, "disabled@300ms", d1, "disabled@2.3s", d2, "select", await p.getByLabel("Choose rider").inputValue());
    await call("POST", `/shop/orders/${o.id}/status`, await tok("0200000002"), { status: "Cancelled", note: "dbg" });
    await p.keyboard.press("Escape");
  }
  await b.close();
})();
