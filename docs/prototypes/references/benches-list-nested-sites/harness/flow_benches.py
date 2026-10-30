"""Drive the real ported benches list (Page.vue + BenchRow.vue + DeployAppsDialog.vue) with faked data."""
import json
import sys

from playwright.sync_api import sync_playwright

url, out = sys.argv[1], sys.argv[2]
results = []


def check(label, ok, detail=""):
	results.append(ok)
	print(f"{'ok  ' if ok else 'FAIL'}  {label}{(' -> ' + detail) if detail else ''}")


with sync_playwright() as p:
	b = p.chromium.launch()
	pg = b.new_page(viewport={"width": 1440, "height": 900})
	errors = []
	# CustomAlerts / LinkControl fetch from a backend this static preview does not have.
	pg.on("pageerror", lambda e: None if "is not valid JSON" in str(e) else errors.append(str(e)))
	pg.goto(url)
	pg.wait_for_selector("text=Accurate System Bench 15", timeout=15000)
	check("3 bench rows render", pg.get_by_text("Accurate System Bench 15").count() == 1 and pg.get_by_text("Onboarding Suite Staging").count() == 1)
	check("apps column shows the app list", pg.get_by_text("frappe, erpnext, hrms, payments, ksa_compliance").count() == 1)
	check("awaiting-deploy status shows", pg.get_by_text("Awaiting Deploy").count() == 1)

	pg.get_by_text("Accurate System Bench 15").first.locator("xpath=ancestor::div[contains(@class,'bench-grid')][1]").click(position={"x": 8, "y": 10})
	pg.wait_for_timeout(500)
	check("expanding a bench lists its 3 sites", pg.get_by_text("accuhub-dev-v15.sandbox.mvpstorm.com").count() == 1 and pg.get_by_text("tchworx.sandbox.mvpstorm.com").count() == 1)
	site_call = next(c for c in pg.evaluate("window.__calls") if c["method"] == "list:Site")
	check("site query asks for server + cluster, filtered by bench", site_call["args"]["filters"].get("group") == "bench-0015" and "server" in site_call["args"]["fields"], json.dumps(site_call["args"]["filters"]))
	pg.screenshot(path=f"{out}/real-expanded.png")

	row = pg.get_by_text("Accurate System Bench 15").first.locator("xpath=ancestor::div[contains(@class,'bench-grid')][1]")
	row.locator("button").last.click()
	pg.wait_for_timeout(300)
	items = [t for t in ("Add Site", "App Marketplace", "Bench Actions", "Drop bench") if pg.get_by_text(t, exact=True).count()]
	check("bench menu has the 4 actions", len(items) == 4, ", ".join(items))
	pg.screenshot(path=f"{out}/real-bench-menu.png")
	pg.get_by_text("Add Site", exact=True).click()
	pg.wait_for_timeout(300)
	check("Add Site opens our new-site route for this bench", "/r5/" in pg.url and "bench-0015" in pg.url, pg.url.split("#")[-1])
	pg.go_back()
	pg.wait_for_selector("text=Onboarding Suite Staging")

	pg.get_by_text("Onboarding Suite Staging").first.locator("xpath=ancestor::div[contains(@class,'bench-grid')][1]").locator("button.p-1").click()
	pg.wait_for_timeout(800)
	dialog = pg.get_by_role("dialog")
	check("deploy dialog opens", dialog.count() >= 1 and pg.get_by_text("Deploy apps to your bench").count() == 1)
	check("dialog shows the server title from the list query", pg.get_by_text("press-f1 (Hetzner, Falkenstein)").count() >= 1)
	pg.locator("[role=dialog] label").nth(0).click()
	pg.locator("[role=dialog] label").nth(1).click()
	pg.wait_for_timeout(200)
	btn = pg.get_by_role("button", name="Deploy 2 apps")
	check("picking 2 apps updates the button", btn.count() == 1)
	pg.screenshot(path=f"{out}/real-deploy-dialog.png")
	btn.click()
	pg.wait_for_timeout(800)
	methods = [c["method"] for c in pg.evaluate("window.__calls")]
	check("deploy calls add_apps then deploy_and_update", methods.index("press.api.bench.add_apps") < methods.index("press.api.bench.deploy_and_update") if "press.api.bench.deploy_and_update" in methods else False)
	check("toast confirms the deploy", pg.get_by_text("Deploy started for Onboarding Suite Staging").count() == 1)

	pg.get_by_placeholder("Search bench").fill("hstp")
	pg.wait_for_timeout(900)
	check("search filters rows", pg.get_by_text("HSTP staging", exact=True).count() == 1 and pg.get_by_text("Onboarding Suite Staging", exact=True).count() == 0)
	pg.get_by_placeholder("Search bench").fill("")
	pg.wait_for_timeout(900)
	row = pg.get_by_text("HSTP staging", exact=True).locator("xpath=ancestor::div[contains(@class,'bench-grid')][1]")
	row.locator("button").last.click()
	pg.get_by_text("Drop bench", exact=True).click()
	pg.wait_for_timeout(500)
	check("drop dialog warns about the linked version upgrade", pg.get_by_text("dropping this will cancel the site upgrade").count() == 1)
	doc_calls = [c for c in pg.evaluate("window.__calls") if c["method"] == "doc:Release Group"]
	check("drop loads only that bench's doc", len(doc_calls) == 1 and doc_calls[0]["args"]["name"] == "bench-0044")
	pg.screenshot(path=f"{out}/real-drop-dialog.png")
	before = len([c for c in pg.evaluate("window.__calls") if c["method"] == "list:Release Group"])
	pg.locator("[role=dialog] input").last.fill("HSTP staging")
	pg.get_by_role("button", name="Drop").click()
	pg.wait_for_timeout(600)
	after = len([c for c in pg.evaluate("window.__calls") if c["method"] == "list:Release Group"])
	deleted = [c for c in pg.evaluate("window.__calls") if c["method"] == "delete:Release Group"]
	check("Drop deletes the bench and reloads the list", len(deleted) == 1 and after == before + 1, f"list loads {before} -> {after}")
	print("page errors:", errors or "none")
	b.close()
sys.exit(0 if all(results) and not errors else 1)
