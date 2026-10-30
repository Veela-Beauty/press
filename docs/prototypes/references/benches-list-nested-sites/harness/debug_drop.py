"""Debug why the drop confirm dialog does not show."""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
	b = p.chromium.launch()
	pg = b.new_page(viewport={"width": 1440, "height": 900})
	logs = []
	pg.on("pageerror", lambda e: logs.append("pageerror: " + str(e)[:300]))
	pg.on("console", lambda m: logs.append(f"console.{m.type}: {m.text[:300]}"))
	pg.goto("http://localhost:5199/benches.html")
	pg.wait_for_selector("text=HSTP staging")
	row = pg.get_by_text("HSTP staging", exact=True).locator("xpath=ancestor::div[contains(@class,'bench-grid')][1]")
	row.locator("button").last.click()
	pg.get_by_text("Drop bench", exact=True).click()
	pg.wait_for_timeout(1500)
	print("dialogs in DOM:", pg.locator("[role=dialog]").count())
	print("queued dialogs:", pg.evaluate("window.__dialogs.value.map(d => ({ id: d.id, type: d.type?.name || d.type?.__name || typeof d.type, props: Object.keys(d.props || {}) }))"))
	print("\n".join(l for l in logs if "valid JSON" not in l) or "no logs")
	b.close()
