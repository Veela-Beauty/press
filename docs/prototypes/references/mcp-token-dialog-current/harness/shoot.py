"""Screenshot the deployed Issue MCP Token dialog: as it opens, and after picking a confidential site."""
import sys

from playwright.sync_api import sync_playwright

url, out = sys.argv[1], sys.argv[2]
with sync_playwright() as p:
	b = p.chromium.launch()
	pg = b.new_page(viewport={"width": 1440, "height": 900})
	errors = []
	pg.on("pageerror", lambda e: errors.append(str(e)))
	pg.goto(url)
	pg.wait_for_selector("text=Issue MCP Token", timeout=15000)
	pg.wait_for_timeout(800)
	dialog = pg.locator("[role=dialog]").first
	dialog.screenshot(path=f"{out}/01-opens.png")
	sites = pg.get_by_placeholder("Search sites...")
	sites.scroll_into_view_if_needed()
	sites.click()
	pg.get_by_text("accuhub-dev-v15.sandbox.mvpstorm.com").first.click()
	pg.wait_for_timeout(300)
	dialog.screenshot(path=f"{out}/02-confidential-site-picked.png")
	box = dialog.bounding_box()
	print("dialog box:", {k: round(v) for k, v in box.items()})
	print("page errors:", errors or "none")
	b.close()
