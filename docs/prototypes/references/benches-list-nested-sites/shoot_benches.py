"""Screenshot the benches-list prototype (default, row menu open, filtered) and run the layout probe."""
import json
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
	pg.wait_for_timeout(500)
	pg.screenshot(path=str(out / "01-default.png"), full_page=True)
	pg.locator(".row").nth(0).locator("button.icon").click()
	pg.wait_for_timeout(150)
	pg.screenshot(path=str(out / "02-bench-menu.png"))
	pg.mouse.click(700, 20)
	pg.fill("#q", "accurate")
	pg.wait_for_timeout(150)
	pg.screenshot(path=str(out / "03-search-accurate.png"))
	pg.fill("#q", "")
	pg.wait_for_timeout(150)
	pg.locator("button.rocket").first.click()
	pg.locator(".app-card input").nth(0).check()
	pg.locator(".app-card input").nth(1).check()
	pg.wait_for_timeout(150)
	print("deploy dialog:", pg.locator(".where").inner_text().replace("\n", " "), "|", pg.locator("#deploy-btn").inner_text())
	pg.screenshot(path=str(out / "05-deploy-dialog.png"))
	pg.locator(".dialog h3 button").click()
	for w in (1440, 1280, 1024, 768, 375):
		pg.set_viewport_size({"width": w, "height": 900})
		d = pg.evaluate(f"({probe})()").get("derived", {})
		print(w, {k: (v.get("score"), v.get("why")) for k, v in d.items() if isinstance(v, dict) and "score" in v})
	pg.set_viewport_size({"width": 375, "height": 900})
	pg.screenshot(path=str(out / "04-mobile-375.png"), full_page=True)
	print("page errors:", errors or "none")
	b.close()
