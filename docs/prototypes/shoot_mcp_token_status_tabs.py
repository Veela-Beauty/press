"""Screenshot the MCP token status tabs prototype: each tab at 1100 px, Active at 768 and 375 px."""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
PAGE = (HERE / "mcp_token_status_tabs_prototype.html").as_uri()
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "mcp_token_status_tabs"
OUT.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
	browser = p.chromium.launch()
	page = browser.new_page(viewport={"width": 1180, "height": 760})
	page.goto(PAGE)
	for tab in ("Active", "Revoked", "Expired"):
		page.get_by_role("button", name=tab).click()
		page.screenshot(path=str(OUT / f"{tab.lower()}-1180.png"), full_page=True)
	page.get_by_role("button", name="Active").click()
	for width in (768, 375):
		page.set_viewport_size({"width": width, "height": 900})
		page.screenshot(path=str(OUT / f"active-{width}.png"), full_page=True)
		overflow = page.evaluate("document.documentElement.scrollWidth > window.innerWidth")
		print(f"{width}px horizontal overflow: {overflow}")
	browser.close()
print("saved to", OUT)
