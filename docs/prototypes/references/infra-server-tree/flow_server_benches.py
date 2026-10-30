"""Server Benches tab in embedded mode: server filter, no page header, New Bench targets this server."""
import sys

from playwright.sync_api import sync_playwright

base, out = sys.argv[1], sys.argv[2]
ok = []


def check(label, cond, detail=""):
	ok.append(cond)
	print(f"{'ok  ' if cond else 'FAIL'}  {label}{(' -> ' + str(detail)) if detail != '' else ''}")


with sync_playwright() as p:
	b = p.chromium.launch()
	pg = b.new_page(viewport={"width": 1440, "height": 700})
	errors = []
	pg.on("pageerror", lambda e: None if "valid JSON" in str(e) else errors.append(str(e)))
	pg.goto(base + "/server-benches.html")
	pg.wait_for_selector("text=Accurate System Bench 15", timeout=15000)
	first = [c for c in pg.evaluate("window.__calls") if c["method"] == "list:Release Group"][0]
	check("list query filtered by this server", first["args"]["filters"].get("server") == "u4-default.sandbox.mvpstorm.com", first["args"]["filters"])
	check("no page header / breadcrumb (server page has its own)", pg.get_by_role("link", name="Benches").count() == 0)
	check("tree rows render (chevron + sites count)", pg.locator(".bench-grid").count() >= 3)
	pg.get_by_text("Accurate System Bench 15").first.locator("xpath=ancestor::div[contains(@class,'bench-grid')][1]").click(position={"x": 8, "y": 10})
	pg.wait_for_timeout(400)
	check("bench expands to its sites", pg.get_by_text("accuhub-dev-v15.sandbox.mvpstorm.com").count() == 1)
	pg.screenshot(path=f"{out}/server-benches-tab.png")
	nb = pg.get_by_role("button", name="New Bench")
	check("New Bench shown for an Active server", nb.count() == 1)
	nb.click()
	pg.wait_for_timeout(300)
	check("New Bench creates on this server", "/r1/u4-default.sandbox.mvpstorm.com" in pg.url, pg.url.split("#")[-1])
	pg.goto(base + "/server-benches.html?active=0")
	pg.wait_for_selector("text=Accurate System Bench 15", timeout=15000)
	check("New Bench hidden when the server is not Active", pg.get_by_role("button", name="New Bench").count() == 0)
	print("page errors:", errors or "none")
	b.close()
sys.exit(0 if all(ok) and not errors else 1)
