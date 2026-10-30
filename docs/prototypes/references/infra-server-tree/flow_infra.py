"""Drive the infra tree prototype: Stop (with confirm) and Start a container."""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

proto, out = Path(sys.argv[1]).resolve(), sys.argv[2]
ok = []


def check(label, cond, detail=""):
	ok.append(cond)
	print(f"{'ok  ' if cond else 'FAIL'}  {label}{(' -> ' + detail) if detail else ''}")


with sync_playwright() as p:
	b = p.chromium.launch()
	pg = b.new_page(viewport={"width": 1440, "height": 900})
	errors = []
	pg.on("pageerror", lambda e: errors.append(str(e)))
	pg.goto(proto.as_uri())
	row = pg.locator("tr.child", has_text="moonsab-redis")
	check("running container shows Restart, Stop, Logs without hovering", all(row.get_by_role("button", name=n).is_visible() for n in ("Restart", "Stop", "Logs")))
	check("stopped container shows Start + Logs", pg.locator("tr.child", has_text="moonsab-mc").get_by_role("button", name="Start").is_visible())
	row.get_by_role("button", name="Stop").click()
	check("Stop asks first", pg.locator("#c-title").inner_text() == "Stop moonsab-redis?", pg.locator("#c-body").inner_text())
	pg.screenshot(path=f"{out}/04-stop-confirm.png")
	pg.locator("#confirm").get_by_role("button", name="Stop").click()
	row = pg.locator("tr.child", has_text="moonsab-redis")
	check("after Stop the row shows exited + a Start button", "exited" in row.inner_text() and row.get_by_role("button", name="Start").is_visible())
	pg.screenshot(path=f"{out}/05-after-stop.png")
	row.get_by_role("button", name="Start").click()
	check("Start brings it back to running", "running" in pg.locator("tr.child", has_text="moonsab-redis").inner_text())
	print("page errors:", errors or "none")
	b.close()
sys.exit(0 if all(ok) and not errors else 1)
