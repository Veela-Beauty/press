"""Run the ui-ux-ba layout probe on the MCP token status tabs prototype at 5 widths (Gate 5, L1/L2/L3/L6/L10)."""
import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

PAGE = (Path(__file__).resolve().parent / "mcp_token_status_tabs_prototype.html").as_uri()
PROBE_FILE = Path.home() / ".claude/skills/ui-ux-ba/scripts/layout_probe.js"
PROBE = re.sub(r"^\s*//.*$", "", PROBE_FILE.read_text(), flags=re.M).strip()

with sync_playwright() as p:
	browser = p.chromium.launch()
	page = browser.new_page()
	page.goto(PAGE)
	for width in (1440, 1280, 1024, 768, 375):
		page.set_viewport_size({"width": width, "height": 900})
		result = page.evaluate(f"({PROBE})()")
		print(width, json.dumps({"derived": result.get("derived"), "overflow": result.get("overflow")}, default=str)[:900])
	browser.close()
