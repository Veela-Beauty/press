"""Screenshot the infra tree prototype and run the layout probe."""
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

proto, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
probe = re.sub(r"^\s*//.*$", "", Path.home().joinpath(".claude/skills/ui-ux-ba/scripts/layout_probe.js").read_text(), flags=re.M).strip()
with sync_playwright() as p:
	b = p.chromium.launch()
	pg = b.new_page(viewport={"width": 1440, "height": 900})
	errors = []
	pg.on("pageerror", lambda e: errors.append(str(e)))
	pg.goto(proto.as_uri())
	pg.wait_for_timeout(400)
	print("container rows shown:", pg.locator("tr.child").count(), "| show-more link:", pg.locator("tr.more").inner_text().strip())
	pg.screenshot(path=str(out / "01-managed-host-expanded.png"), full_page=True)
	pg.locator("tr.more .link").click()
	print("after show more:", pg.locator("tr.child").count())
	pg.locator("#row-daytona-sandbox-1").click()
	pg.locator("[id='row-press-f1.sandbox.mvpstorm.com']").click()
	pg.wait_for_timeout(200)
	pg.screenshot(path=str(out / "02-press-server-expanded.png"), full_page=True)
	pg.locator("[id='row-daytona-sandbox-1']").click()
	pg.locator("button[title=Logs]").first.click()
	pg.wait_for_timeout(200)
	print("logs panel:", pg.locator("#d-title").inner_text())
	pg.screenshot(path=str(out / "03-logs-panel.png"))
	pg.locator("#drawer .icon-btn").click()
	for w in (1440, 1280, 1024, 768, 375):
		pg.set_viewport_size({"width": w, "height": 900})
		d = pg.evaluate(f"({probe})()").get("derived", {})
		print(w, {k: v.get("score") for k, v in d.items() if isinstance(v, dict) and "score" in v}, "| overflow:", pg.evaluate("document.documentElement.scrollWidth > innerWidth"))
	print("page errors:", errors or "none")
	b.close()
