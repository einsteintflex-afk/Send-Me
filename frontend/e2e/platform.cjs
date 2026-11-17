// Full-platform journey: student -> shop -> rider -> tracking -> admin. Needs a fresh demo DB (python -m app.seed_demo).
const { chromium } = require("playwright");
const BASE = process.env.BASE || "http://localhost:8000"; const SHOTS = process.env.SHOTS || "/tmp";
const ok = (c, m) => { if (!c) throw new Error("FAIL: " + m); console.log("ok  " + m); };
const call = async (method, path, token, body) => { const r = await fetch(BASE + path, { method, headers: { "Content-Type": "application/json", ...(token ? { Authorization: "Bearer " + token } : {}) }, body: body ? JSON.stringify(body) : undefined }); const j = await r.json().catch(() => ({})); if (!r.ok) throw new Error(`${method} ${path}: ${JSON.stringify(j)}`); return j; };
const tok = async (id) => (await call("POST", "/auth/login", null, { identifier: id, password: "demo12345" })).access_token;

async function login(page, phone, expectText) {
  await page.goto(BASE + "/#/login"); await page.getByLabel("Phone or email").fill(phone); await page.getByLabel("Password").fill("demo12345"); await page.getByRole("button", { name: "Sign in" }).click(); await page.getByText(expectText).first().waitFor();
}
(async () => {
  const b = await chromium.launch(); const errs = [];
  const mk = async (w, h, geo) => { const c = await b.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1, geolocation: geo, permissions: geo ? ["geolocation"] : [] }); const p = await c.newPage(); p.on("pageerror", (e) => errs.push(e.message)); p.on("console", (m) => m.type() === "error" && !/tile\.openstreetmap|ERR_|Failed to load resource/.test(m.text()) && errs.push(m.text())); return p; };
  const shot = (p, n) => p.screenshot({ path: `${SHOTS}/${n}.png` });

  // --- student places and pays for an order (API for speed; UI journey is covered by student.cjs)
  const st = await tok("0200000003");
  const prods = (await call("GET", "/products?q=bread")).items; const bread = prods.find((p) => p.name === "Bread");
  await call("POST", "/cart/items", st, { product_id: bread.id, quantity: 2 });
  const shop = (await call("GET", "/shops"))[0];
  await call("POST", "/cart/requests", st, { shop_id: shop.id, name: "Dettol soap", brand: "Dettol", quantity: 1 });
  const addr = (await call("GET", "/auth/addresses", st))[0];
  const order = await call("POST", "/checkout", st, { address_id: addr.id, instructions: "Call when you arrive" });
  const pay = await call("POST", `/orders/${order.id}/pay`, st, {}); await call("POST", `/dev/mock-pay/${pay.reference}`, st, { outcome: "success" }); await call("POST", `/payments/verify/${pay.reference}`, st, {});
  ok(true, "student order placed and paid (simulated)");

  // --- shop dashboard
  const shopP = await mk(1100, 800); await login(shopP, "0200000002", "Shop dashboard"); await shot(shopP, "20-shop-overview");
  ok(await shopP.getByText(/new order/).count() > 0, "shop sees the new order alert");
  await shopP.getByRole("link", { name: /Orders/ }).click(); await shopP.getByText("Needs your response").first().click(); await shopP.getByRole("button", { name: "Accept order" }).waitFor(); await shot(shopP, "21-shop-order");
  await shopP.getByRole("button", { name: "Accept order" }).click(); await shopP.getByRole("button", { name: "Start preparing" }).click();
  await shopP.getByLabel("Choose rider").selectOption({ label: "Demo Rider (020 000 0004)" });
  try { await shopP.getByRole("button", { name: "Assign", exact: true }).click({ timeout: 5000 }); } catch (e) { await shot(shopP, "99-assign-fail"); console.log("select value:", await shopP.getByLabel("Choose rider").inputValue(), "| buttons:", (await shopP.getByRole("button").allInnerTexts()).join(" / ")); throw e; } await shopP.getByText("not accepted yet").waitFor(); ok(true, "shop accepted, prepared and assigned rider"); await shot(shopP, "22-shop-assigned");
  await shopP.keyboard.press("Escape");

  // --- shop: item request, products
  await shopP.getByRole("link", { name: /Item requests/ }).click(); await shopP.getByText("1 × Dettol soap").waitFor(); await shopP.getByLabel("Price for Dettol soap").fill("12.50"); await shopP.getByRole("button", { name: "Send price" }).click(); await shopP.getByText("Price sent to the student").waitFor(); ok(true, "shop priced the unlisted item"); await shot(shopP, "23-shop-requests");
  await shopP.getByRole("link", { name: "Products" }).click(); await shopP.getByLabel("Price for Bread").waitFor(); await shopP.getByLabel("Price for Bread").fill("26"); await shopP.getByLabel("Price for Bread").blur(); await shopP.waitForTimeout(500);
  ok((await call("GET", `/products/${bread.id}`)).price === 26, "shop price edit saved to backend"); await shot(shopP, "24-shop-products");
  await call("PATCH", `/shop/products/${bread.id}?`, await tok("0200000002"), { price: "25.00" });

  // --- rider app (phone, no email)
  const riderP = await mk(390, 844, { latitude: 5.6500, longitude: -0.1870 }); await login(riderP, "0200000004", "Assigned to you"); await shot(riderP, "25-rider-list");
  await riderP.getByText("Tap to accept").click(); await riderP.getByRole("button", { name: "Accept delivery" }).click(); await riderP.getByRole("button", { name: "I've picked up the order" }).click(); await riderP.getByRole("button", { name: "Mark as delivered" }).waitFor();
  ok(true, "rider accepted and picked up (order On the Way)"); await riderP.getByRole("button", { name: /simulate moving/ }).click(); await riderP.waitForTimeout(800); await riderP.getByText("Navigate to customer").waitFor(); await shot(riderP, "26-rider-delivery");
  ok(await riderP.getByRole("link", { name: /Navigate to customer/ }).getAttribute("href").then((h) => h.includes("google.com/maps/dir")), "rider has navigation link");

  // --- student tracks
  const stP = await mk(390, 844); await login(stP, "0200000003", "What do you need today?"); await stP.goto(BASE + `/#/orders/${order.id}`); await stP.getByText("● Live").waitFor({ timeout: 15000 }); await stP.waitForTimeout(1200); await shot(stP, "27-student-tracking");
  ok(await stP.getByText(/away/).count() > 0, "student sees live rider location and distance"); ok(await stP.getByText("Demo Rider").count() > 0, "rider name shown to student");
  const t = await call("GET", `/orders/${order.id}/tracking`, st); ok(t.live && t.rider_position, "tracking API live");

  // --- rider delivers
  await riderP.getByRole("button", { name: "Mark as delivered" }).click(); await riderP.getByText("Delivered", { exact: true }).first().waitFor(); ok(true, "rider marked delivered");
  await stP.reload(); await stP.getByText("You've received your order.").waitFor(); ok(true, "student sees Delivered"); await shot(stP, "28-student-delivered");

  // --- admin
  const adP = await mk(1100, 800); await login(adP, "0200000001", "Administrator"); await adP.waitForTimeout(600); await shot(adP, "30-admin-overview");
  ok(await adP.getByText("Revenue (paid)").count() > 0, "admin overview");
  await adP.getByRole("link", { name: "Riders" }).click(); await adP.getByRole("button", { name: /Add rider/ }).click();
  await adP.getByLabel("Full name").fill("Sammy Test"); await adP.getByLabel("Phone number").fill("0264944652"); await adP.getByLabel("Password").fill("sammytest1"); await adP.getByRole("button", { name: "Create rider" }).click(); await adP.getByText("Sammy Test").waitFor(); ok(true, "admin created rider with phone and no email"); await shot(adP, "31-admin-riders");
  const sammy = await call("POST", "/auth/login", null, { identifier: "0264944652", password: "sammytest1" }); ok(!!sammy.access_token, "new rider signs in with phone only");
  for (const [name, text] of [["Delivery", "Distance pricing"], ["System", "Payments (Paystack)"], ["Payments", "Reference"], ["Shops", "Participating shops"], ["Students", "Name"], ["Orders", "Order"]]) { await adP.getByRole("link", { name, exact: true }).click(); await adP.getByText(text).first().waitFor(); await adP.waitForTimeout(300); if (["Delivery", "System"].includes(name)) await shot(adP, "32-admin-" + name.toLowerCase()); }
  ok(true, "admin pages load");
  const msgs = await call("GET", "/notifications", st); ok(msgs.some((n) => n.kind === "request_priced"), "student was notified of the quoted price");
  ok(errs.length === 0, "no browser errors " + errs.slice(0, 3).join(" | "));
  await b.close();
})().catch((e) => { console.error(e.message); process.exit(1); });
