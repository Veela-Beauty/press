"""Measure how much of a 1750px content area the Tessera page uses, before vs after."""
import sys

from playwright.sync_api import sync_playwright

base, out = sys.argv[1], sys.argv[2]
with sync_playwright() as p:
	b = p.chromium.launch()
	pg = b.new_page(viewport={"width": 1750, "height": 700})  # the user's content area: 2000 px screen minus 250 px sidebar
	errors = []
	pg.on("pageerror", lambda e: None if "valid JSON" in str(e) else errors.append(str(e)[:160]))
	for v in ("before", "after"):
		pg.goto(f"{base}/tessera.html?v={v}")
		pg.wait_for_timeout(1500)
		box = pg.evaluate("""() => {
			const root = document.querySelector('#content > *');
			const r = root.getBoundingClientRect();
			const inner = [...root.querySelectorAll('*')].map(e => e.getBoundingClientRect()).filter(x => x.width > 0);
			const left = Math.min(...inner.map(x => x.left)), right = Math.max(...inner.map(x => x.right));
			return { root_width: Math.round(r.width), content_left: Math.round(left), content_right: Math.round(right), viewport: innerWidth };
		}""")
		used = round((box["content_right"] - box["content_left"]) / box["viewport"] * 100)
		print(f"{v:6} content spans x={box['content_left']}..{box['content_right']} of {box['viewport']} px -> {used}% used, white space each side ~{box['content_left']} / {box['viewport'] - box['content_right']} px")
		pg.screenshot(path=f"{out}/tessera-{v}.png")
	print("page errors:", errors or "none")
	b.close()
