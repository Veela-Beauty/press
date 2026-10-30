"""Check the Version / Tag filters render on the ported benches page."""
import sys

from playwright.sync_api import sync_playwright

url, shot = sys.argv[1], sys.argv[2]
with sync_playwright() as p:
	b = p.chromium.launch()
	pg = b.new_page(viewport={"width": 1440, "height": 400})
	errs = []
	pg.on("pageerror", lambda e: errs.append(str(e)[:160]))
	pg.goto(url)
	pg.wait_for_selector("text=HSTP staging")
	pg.wait_for_timeout(800)
	found = pg.evaluate(
		"[...document.querySelectorAll('input,button')].map(e => e.placeholder || e.innerText).filter(t => /Version|Tag/.test(t))"
	)
	print("filter controls found:", found)
	pg.screenshot(path=shot)
	print("errors:", errs or "none")
	b.close()
