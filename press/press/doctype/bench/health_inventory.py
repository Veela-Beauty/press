"""
App inventory scanners — hooks interactions + scripts/reports counts.
Called from bench_code_health.py (the @whitelist stub).
"""

import re

from .bench_code_health import _exec, UPSTREAM_APPS


def scan_app_interactions(bench):
    """Scan hooks.py per app — returns doc_events, scheduler, overrides."""
    r = _exec(bench, "ls apps/")
    apps = [a.strip() for a in r.get("output", "").split() if a.strip()]

    results = []
    for app in apps:
        r = _exec(bench, f"cat apps/{app}/{app}/hooks.py 2>/dev/null || echo __MISSING__")
        content = r.get("output", "")
        if "__MISSING__" in content:
            continue

        info = {"app": app, "doc_events": [], "scheduler_events": [],
                "overrides": [], "has_boot_session": False}

        if "doc_events" in content:
            info["doc_events"] = re.findall(
                r'["\']([A-Z][^"\']+)["\']:\s*\{', content[content.find("doc_events"):]
            )[:30]

        for freq in ("daily", "hourly", "weekly", "monthly", "cron",
                     "daily_long", "weekly_long", "all"):
            if f'"{freq}"' in content or f"'{freq}'" in content:
                info["scheduler_events"].append(freq)

        if "override_whitelisted_methods" in content:
            idx = content.find("override_whitelisted_methods")
            info["overrides"] = re.findall(r'["\']([^"\']+)["\']:', content[idx:idx + 600])[:15]

        info["has_boot_session"] = ("extend_bootinfo" in content or "boot_session" in content)
        results.append(info)
    return results


def scan_scripts_inventory(bench):
    """Inventory: client scripts, controllers, whitelisted methods, reports per app."""
    r = _exec(bench, "ls apps/")
    apps = [a.strip() for a in r.get("output", "").split() if a.strip()]

    results = []
    for app in apps:
        if app in UPSTREAM_APPS:
            continue

        counts = {}
        cmds = {
            "client_scripts": f"find apps/{app} -name '*.js' -path '*/doctype/*' -not -path '*node_modules*' | wc -l",
            "controllers": f"find apps/{app} -name '*.py' -path '*/doctype/*' -not -name '__init__*' -not -path '*__pycache__*' | wc -l",
            "whitelisted": f"grep -r -c '@frappe.whitelist' apps/{app}/ --include='*.py' 2>/dev/null | awk -F: '{{s+=$2}} END {{print s+0}}'",
            "reports": f"find apps/{app} -path '*/report/*' -name '*.py' -not -name '__init__*' | wc -l",
            "fixtures": f"find apps/{app} -name 'custom_field.json' -o -name 'fixtures' -type d 2>/dev/null | wc -l",
        }
        for key, cmd in cmds.items():
            out = _exec(bench, cmd)
            counts[key] = int(out.get("output", "0").strip() or 0)

        counts["app"] = app
        results.append(counts)
    return results
