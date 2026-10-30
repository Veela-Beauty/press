"""Screenshot deployed vs new sidebar and read their computed size and colors."""
import json
import sys

from playwright.sync_api import sync_playwright

url, out = sys.argv[1], sys.argv[2]
MEASURE = """(id) => {
  const root = document.querySelector(id + ' .as-sidebar');
  const item = document.querySelector(id + ' .as-nav-inactive');
  const active = document.querySelector(id + ' .as-nav-active');
  const icon = item.querySelector('.as-nav-icon');
  const label = item.querySelector('span.text-\\\\[13px\\\\], span.text-\\\\[13\\\\.5px\\\\]');
  const cs = (el) => getComputedStyle(el);
  return {
    width: root.getBoundingClientRect().width,
    background: cs(root).backgroundColor,
    item_text: cs(item).color, item_icon: cs(icon).color,
    item_padding: cs(item).padding, item_radius: cs(item).borderRadius,
    font_size: label ? cs(label).fontSize : null,
    active_bg: cs(active).backgroundColor,
    item_height: item.getBoundingClientRect().height,
  };
}"""
with sync_playwright() as p:
	b = p.chromium.launch()
	pg = b.new_page(viewport={"width": 700, "height": 760})
	errors = []
	pg.on("pageerror", lambda e: errors.append(str(e)))
	pg.goto(url)
	pg.wait_for_selector("#after .as-sidebar", timeout=15000)
	pg.wait_for_timeout(500)
	for side in ("before", "after"):
		print(side, json.dumps(pg.evaluate(MEASURE, "#" + side)))
	pg.screenshot(path=f"{out}/sidebar-before-after.png")
	print("page errors:", errors or "none")
	b.close()
