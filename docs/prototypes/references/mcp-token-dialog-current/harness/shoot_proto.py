"""Screenshot every prototype state and run the layout probe at 5 widths."""
import json
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

proto = Path(sys.argv[1]).resolve()
out = Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
probe_src = Path.home().joinpath(".claude/skills/ui-ux-ba/scripts/layout_probe.js").read_text()
# Strip comments so the file body is a bare function expression.
probe_fn = re.sub(r"^\s*//.*$", "", probe_src, flags=re.M).strip()

with sync_playwright() as p:
	b = p.chromium.launch()
	pg = b.new_page(viewport={"width": 1440, "height": 900})
	errors = []
	pg.on("pageerror", lambda e: errors.append(str(e)))
	pg.goto(proto.as_uri())
	pg.wait_for_timeout(600)
	dialog = pg.locator(".dialog")
	for place in ("sites", "top"):
		pg.evaluate(f"setPlace('{place}')")
		for scn in ("plain", "picked", "wrong", "locked", "issued"):
			pg.evaluate(f"scenario('{scn}')")
			dialog.screenshot(path=str(out / f"{place}-{scn}.png"))
	pg.evaluate("setPlace('sites'); scenario('picked')")
	for w in (1440, 1280, 1024, 768, 375):
		pg.set_viewport_size({"width": w, "height": 900})
		res = pg.evaluate(f"({probe_fn})()")
		d = res.get("derived", {})
		ov = res.get("overflow")
		print(w, json.dumps({k: d.get(k) for k in d}, default=str)[:700], "| overflow:", json.dumps(ov)[:160])
	pg.set_viewport_size({"width": 375, "height": 900})
	dialog.screenshot(path=str(out / "sites-picked-375.png"))
	print("page errors:", errors or "none")
	b.close()
