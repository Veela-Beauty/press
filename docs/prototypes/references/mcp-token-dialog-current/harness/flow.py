"""Drive the real IssueTokenDialog.vue: pick a confidential site, no PIN, wrong PIN, right PIN."""
import json
import sys

from playwright.sync_api import sync_playwright

url, out = sys.argv[1], sys.argv[2]
CONF = "accuhub-dev-v15.sandbox.mvpstorm.com"
results = []


def field(pg, label):
	# FormControl wraps label + input in one block; take the input inside the block whose label matches.
	return pg.locator(f"xpath=//label[normalize-space(.)='{label}' or starts-with(normalize-space(.), '{label}')]/ancestor::div[.//input][1]//input").first


def check(label, ok, detail=""):
	results.append(ok)
	print(f"{'ok  ' if ok else 'FAIL'}  {label}{(' -> ' + detail) if detail else ''}")


with sync_playwright() as p:
	b = p.chromium.launch()
	pg = b.new_page(viewport={"width": 1440, "height": 900})
	errors = []
	pg.on("pageerror", lambda e: errors.append(str(e)))
	pg.goto(url)
	pg.wait_for_selector("text=Issue MCP Token", timeout=15000)
	pin = field(pg, "Admin PIN")
	check("no PIN box before any site is picked", pin.count() == 0)

	sites = pg.get_by_placeholder("Search sites...")
	sites.click()
	opt = pg.locator("button", has_text="claudecodelearn.sandbox.mvpstorm.com")
	opt.click()
	check("normal site picked: still no PIN box", field(pg, "Admin PIN").count() == 0)
	conf_opt = pg.locator("button", has_text=CONF)
	check("dropdown tags the confidential site", "confidential" in conf_opt.inner_text(), conf_opt.inner_text().replace("\n", " "))
	conf_opt.click()
	pg.get_by_text("Issue MCP Token").first.click()
	pg.wait_for_timeout(200)
	check("confidential site picked: PIN box shows", field(pg, "Admin PIN").count() == 1)
	check("hint names the site", pg.get_by_text("Unlocks accuhub-dev-v15 for this").count() == 1)

	field(pg, "Label (what this token is for)").fill("accuhub agent")
	field(pg, "Your password (re-auth to issue)").fill("pw")
	issue = pg.get_by_role("button", name="Issue Token")
	issue.click()
	pg.wait_for_timeout(200)
	sent = [c for c in pg.evaluate("window.__calls") if c["method"].endswith("issue_token")]
	check("empty PIN: blocked before calling the server", len(sent) == 0 and pg.get_by_text("Enter the Admin PIN to unlock accuhub-dev-v15").count() == 1)

	field(pg, "Admin PIN").fill("0000")
	issue.click()
	pg.wait_for_timeout(300)
	check("wrong PIN: server error shown", pg.get_by_text("Incorrect PIN").count() == 1)
	check("wrong PIN: PIN box cleared", field(pg, "Admin PIN").input_value() == "")
	pg.locator("[role=dialog]").first.screenshot(path=f"{out}/real-wrong-pin.png")

	field(pg, "Admin PIN").fill("1234")
	issue.click()
	pg.wait_for_timeout(400)
	sent = [c for c in pg.evaluate("window.__calls") if c["method"].endswith("issue_token")]
	last = sent[-1]["args"]
	check("right PIN: sent to issue_token", last.get("confidential_pin") == "1234", json.dumps({k: last[k] for k in ("allowed_sites", "confidential_pin")}))
	check("right PIN: token handed over", pg.get_by_text("pmcp_fake_token_for_render").count() >= 1)
	pg.locator("[role=dialog]").first.screenshot(path=f"{out}/real-issued.png")

	print("page errors:", errors or "none")
	b.close()
sys.exit(0 if all(results) and not errors else 1)
