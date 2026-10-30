"""Drive the real Infrastructure page: expand in place, actions, stop confirm, logs, Needs attention."""
import sys

from playwright.sync_api import sync_playwright

url, out = sys.argv[1], sys.argv[2]
ok = []


def check(label, cond, detail=""):
	ok.append(cond)
	print(f"{'ok  ' if cond else 'FAIL'}  {label}{(' -> ' + str(detail)) if detail != '' else ''}")


def calls(pg, suffix):
	return [c for c in pg.evaluate("window.__calls") if c["method"].endswith(suffix)]


with sync_playwright() as p:
	b = p.chromium.launch()
	pg = b.new_page(viewport={"width": 1440, "height": 900})
	errors = []
	pg.on("pageerror", lambda e: None if "valid JSON" in str(e) else errors.append(str(e)))
	pg.goto(url)
	pg.wait_for_selector("text=daytona-sandbox-1", timeout=15000)
	cell = lambda name: pg.get_by_role("cell", name=name, exact=True)
	check("no container rows before expanding", cell("moonsab-redis").count() == 0)

	pg.locator("#server-row-daytona-sandbox-1").click()
	pg.wait_for_timeout(300)
	check("click expands in place (no dialog)", cell("moonsab-redis").count() == 1 and pg.locator("[role=dialog]").count() == 0)
	check("first 8 containers + show-more link", pg.locator("text=Show 3 more containers").count() == 1)
	check("uptime is short", pg.locator("td", has_text="5w").count() >= 1 and pg.locator("text=Up 5 weeks").count() == 0)
	row = pg.locator("tr", has_text="moonsab-redis")
	check("running row: Restart, Stop, Logs visible without hover", all(row.get_by_role("button", name=n).is_visible() for n in ("Restart", "Stop", "Logs")))
	check("stopped row: Start", pg.locator("tr", has_text="moonsab-mc").get_by_role("button", name="Start").is_visible())
	pg.screenshot(path=f"{out}/real-expanded.png")

	row.get_by_role("button", name="Stop").click()
	pg.wait_for_timeout(400)
	check("Stop asks first", pg.get_by_text("Stop moonsab-redis?").count() == 1)
	check("nothing sent before confirming", len(calls(pg, "host_unit_action")) == 0)
	pg.screenshot(path=f"{out}/real-stop-confirm.png")
	pg.locator("[role=dialog]").get_by_role("button", name="Stop").click()
	pg.wait_for_timeout(500)
	sent = calls(pg, "host_unit_action")
	check("confirm sends stop for that container on that host", len(sent) == 1 and sent[0]["args"]["action"] == "stop" and sent[0]["args"]["host"] == "daytona-sandbox-1", sent[-1]["args"] if sent else "")

	pg.locator("tr", has_text="moonsab-mc").get_by_role("button", name="Start").click()
	pg.wait_for_timeout(400)
	check("Start sends start without asking", calls(pg, "host_unit_action")[-1]["args"]["action"] == "start")

	pg.locator("tr", has_text="postiz").get_by_role("button", name="Logs").click()
	pg.wait_for_timeout(600)
	check("Logs opens the small container drawer", pg.locator("[role=dialog]").count() >= 1 and pg.locator("[role=dialog]", has_text="postiz").count() >= 1)
	pg.keyboard.press("Escape")
	pg.wait_for_timeout(300)

	pg.get_by_text("Show 3 more containers").click()
	pg.wait_for_timeout(200)
	check("show more lists all 11", cell("veela-web").count() == 1)

	pg.locator("[id='server-row-press-f1.sandbox.mvpstorm.com']").click()
	pg.wait_for_timeout(300)
	check("Press server expands to its benches", cell("bench-0015-000122-press-f1").count() == 1)
	dot = pg.locator("tr", has=cell("bench-0015-000122-press-f1")).locator("span.rounded-full").first.get_attribute("class")
	check("healthy bench shows a green dot", "bg-green-500" in dot, dot)
	pg.locator("#server-row-box-1").click()
	pg.wait_for_timeout(300)
	plain = pg.locator("tr", has=cell("sshd.service"))
	check("plain host: Service label, no Logs / Stop buttons", pg.get_by_role("cell", name="Service", exact=True).count() == 1 and plain.get_by_role("button").count() == 0)

	pg.locator("#server-row-daytona-sandbox-1").click()
	pg.wait_for_timeout(200)
	check("click again collapses", cell("moonsab-redis").count() == 0)
	view = pg.get_by_role("button", name="View")
	if view.count():
		view.first.click()
		pg.wait_for_timeout(600)
		check("Needs attention View opens that server in the list", cell("moonsab-redis").count() == 1)
	print("page errors:", errors or "none")
	b.close()
sys.exit(0 if all(ok) and not errors else 1)
