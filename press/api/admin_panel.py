"""Admin Panel API — team management, quotas, features, costs.
All endpoints require desk user (Press admin).
"""
import json

import frappe

from press.utils import get_current_team


def _require_admin():
    """Check that the current user is a Press admin (System User or Administrator)."""
    if frappe.session.user == "Administrator":
        return
    user_type = frappe.db.get_value("User", frappe.session.user, "user_type")
    if user_type == "System User":
        return
    frappe.throw("Only administrators can access the Admin Panel.", frappe.PermissionError)


# Dynamic Feature Registry — role-gated, categorized
# Adding a new tool = add one entry here + create the route/page
DEFAULT_FEATURES = {
    # Backup & Ops
    "daman_backup":    {"label": "Daman Backup",    "icon": "database",   "color": "#2490ef", "category": "ops",
                        "roles": ["Platform Admin", "DevOps Admin", "DevOps User"]},
    # Development
    "dev_overview":    {"label": "Dev Overview",     "icon": "eye",        "color": "#6f42c1", "category": "dev",
                        "roles": ["Platform Admin", "DevOps Admin", "DevOps User", "Developer"]},
    "code_health":     {"label": "Code Health",      "icon": "heartbeat",  "color": "#dc3545", "category": "dev",
                        "roles": ["Platform Admin", "DevOps Admin", "Developer"]},
    "code_server":     {"label": "Code Server",      "icon": "code",       "color": "#28a745", "category": "dev",
                        "roles": ["Platform Admin", "DevOps Admin", "Developer"]},
    "site_dev_tab":    {"label": "Site Dev Tab",     "icon": "terminal",   "color": "#fd7e14", "category": "dev",
                        "roles": ["Platform Admin", "DevOps Admin", "DevOps User", "Developer", "Implementor"]},
    "ai_dev_tab":      {"label": "AI Dev Assistant", "icon": "magic",      "color": "#007bff", "category": "dev",
                        "roles": ["Platform Admin", "DevOps Admin", "Developer"]},
    # Database Tools
    "sql_playground":  {"label": "SQL Playground",   "icon": "table",      "color": "#6f42c1", "category": "db",
                        "roles": ["Platform Admin", "DevOps Admin", "Developer"]},
    "db_analyzer":     {"label": "DB Analyzer",      "icon": "search",     "color": "#17a2b8", "category": "db",
                        "roles": ["Platform Admin", "DevOps Admin", "Developer"]},
    "binlog_browser":  {"label": "Binlog Browser",   "icon": "clock-o",    "color": "#fd7e14", "category": "db",
                        "roles": ["Platform Admin", "DevOps Admin"]},
    "log_browser":     {"label": "Log Browser",      "icon": "file-text",  "color": "#28a745", "category": "db",
                        "roles": ["Platform Admin", "DevOps Admin", "DevOps User", "Developer"]},
    "database_access": {"label": "Database Access",  "icon": "terminal",   "color": "#fd7e14", "category": "db",
                        "roles": ["Platform Admin", "DevOps Admin", "Developer"]},
    # Infrastructure
    "ssh_access":      {"label": "SSH Access",       "icon": "key",        "color": "#dc3545", "category": "infra",
                        "roles": ["Platform Admin", "DevOps Admin"]},
    "private_benches": {"label": "Private Benches",  "icon": "server",     "color": "#8d99a6", "category": "infra",
                        "roles": ["Platform Admin", "DevOps Admin", "DevOps User"]},
    "servers":         {"label": "Servers",          "icon": "cloud",      "color": "#20c997", "category": "infra",
                        "roles": ["Platform Admin", "DevOps Admin"]},
    # Admin
    "admin_panel":     {"label": "Admin Panel",      "icon": "shield",     "color": "#343a40", "category": "admin",
                        "roles": ["Platform Admin"]},
    "partner_admin":   {"label": "Partner Admin",    "icon": "handshake-o","color": "#6610f2", "category": "admin",
                        "roles": ["Platform Admin"]},
    "security_portal": {"label": "Security Portal",  "icon": "lock",       "color": "#6610f2", "category": "admin",
                        "roles": ["Platform Admin", "DevOps Admin"]},
}

# Server costs (Hetzner Cloud pricing, updated manually)
SERVER_COSTS = {
    "press-ctrl.sandbox.mvpstorm.com": {"plan": "CPX51", "cost": 35},
    "press-f1.sandbox.mvpstorm.com": {"plan": "CPX41+disk", "cost": 24},
    "u4-default.sandbox.mvpstorm.com": {"plan": "CX22", "cost": 4},
    "u5-default.sandbox.mvpstorm.com": {"plan": "CX32", "cost": 8},
}


@frappe.whitelist()
def get_feature_registry():
    """Return the list of available features for toggle UI."""
    _require_admin()
    return DEFAULT_FEATURES


@frappe.whitelist()
def get_admin_data():
    """Return all teams with quotas, usage, members, costs."""
    _require_admin()

    teams = frappe.get_all("Team", fields=[
        "name", "user", "enabled", "team_title",
        "max_sites", "max_benches", "max_disk_gb",
        "allowed_site_types", "enabled_features",
    ])

    for team in teams:
        t = team.name
        team["site_count"] = frappe.db.count("Site", {"team": t, "status": ("not in", ("Archived",))})
        team["bench_count"] = frappe.db.count("Release Group", {"team": t, "enabled": 1})
        team["member_count"] = frappe.db.count("Team Member", {"parent": t})

        type_counts = frappe.db.sql(
            "SELECT IFNULL(site_type, 'Production') as t, COUNT(*) as c "
            "FROM tabSite WHERE team=%s AND status NOT IN ('Archived') GROUP BY site_type",
            t, as_dict=True,
        )
        team["site_type_counts"] = {r.t: r.c for r in type_counts}
        team["features"] = json.loads(team.get("enabled_features") or "{}")
        team["cost"] = _calc_team_cost(t)

    stats = {
        "total_teams": len(teams),
        "total_sites": frappe.db.count("Site", {"status": ("not in", ("Archived",))}),
        "total_benches": frappe.db.count("Release Group", {"enabled": 1}),
        "total_cost": sum(s["cost"] for s in _get_server_costs()),
    }

    return {"teams": teams, "stats": stats, "server_costs": _get_server_costs()}


@frappe.whitelist()
def update_team_quotas(team, max_sites=None, max_benches=None, max_disk_gb=None,
                       allowed_site_types=None, enabled_features=None):
    """Update quotas and feature flags for a team."""
    _require_admin()
    updates = {}
    if max_sites is not None:
        updates["max_sites"] = int(max_sites)
    if max_benches is not None:
        updates["max_benches"] = int(max_benches)
    if max_disk_gb is not None:
        updates["max_disk_gb"] = float(max_disk_gb)
    if allowed_site_types is not None:
        # Normalize: strip whitespace, remove empty lines, standardize newlines
        lines = [t.strip() for t in allowed_site_types.replace("\r\n", "\n").split("\n") if t.strip()]
        updates["allowed_site_types"] = "\n".join(lines)
    if enabled_features is not None:
        updates["enabled_features"] = (
            enabled_features if isinstance(enabled_features, str)
            else json.dumps(enabled_features)
        )
    for field, value in updates.items():
        frappe.db.set_value("Team", team, field, value)
    frappe.db.commit()
    return {"ok": True}


@frappe.whitelist()
def toggle_team(team, action):
    """Block or unblock a team."""
    _require_admin()
    team_doc = frappe.get_doc("Team", team)
    if action == "block":
        team_doc.ban()
    elif action == "unblock":
        team_doc.enabled = 1
        team_doc.save(ignore_permissions=True)
        team_doc.unsuspend_sites()
    else:
        frappe.throw(f"Unknown action: {action}")
    frappe.db.commit()
    return {"ok": True}


@frappe.whitelist()
def get_team_members(team):
    """Return members of a team."""
    _require_admin()
    members = frappe.get_all("Team Member", {"parent": team}, ["user", "press_role"])
    result = []
    for m in members:
        user = frappe.get_value("User", m.user, ["full_name", "last_active", "creation"], as_dict=True)
        result.append({
            "user": m.user,
            "full_name": user.full_name if user else "",
            "joined": user.creation if user else "",
            "last_active": user.last_active if user else "",
            "press_role": m.press_role or "Viewer",
        })
    return result


@frappe.whitelist()
def set_member_role(team, user, role):
    """Set the press_role for a team member."""
    _require_admin()
    from press.press.doctype.team.team_roles import PRESS_ROLES
    if role not in PRESS_ROLES:
        frappe.throw(f"Invalid role: {role}")
    member = frappe.get_value("Team Member", {"parent": team, "user": user}, "name")
    if not member:
        frappe.throw(f"User {user} is not a member of team {team}")
    frappe.db.set_value("Team Member", member, "press_role", role)
    frappe.db.commit()
    return {"ok": True}


@frappe.whitelist()
def get_roles():
    """Return available press roles."""
    from press.press.doctype.team.team_roles import PRESS_ROLES
    return PRESS_ROLES


@frappe.whitelist()
def reset_user_password(user, new_password):
    """Reset a user's password."""
    _require_admin()
    if not new_password or len(new_password) < 8:
        frappe.throw("Password must be at least 8 characters.")
    from frappe.utils.password import update_password
    update_password(user, new_password)
    return {"ok": True}


@frappe.whitelist()
def get_team_sites(team):
    """Return all sites for a team."""
    _require_admin()
    return frappe.get_all("Site", {"team": team, "status": ("not in", ("Archived",))},
                          ["name", "status", "site_type", "group", "bench", "server", "creation"],
                          order_by="creation desc")


@frappe.whitelist()
def get_team_benches(team):
    """Return all benches for a team."""
    _require_admin()
    benches = frappe.get_all("Release Group", {"team": team, "enabled": 1},
                             ["name", "title", "version", "creation"],
                             order_by="creation desc")
    for b in benches:
        b["site_count"] = frappe.db.count("Site", {"group": b.name, "status": ("not in", ("Archived",))})
        servers = frappe.get_all("Bench", {"group": b.name, "status": "Active"},
                                 ["server"], distinct=True, pluck="server")
        b["servers"] = servers
        b["is_dev"] = any(
            frappe.get_value("Bench", {"group": b.name, "server": s, "status": "Active"},
                             "is_development_bench")
            for s in servers
        ) if servers else False
    return benches


@frappe.whitelist()
def create_team_from_admin(email, full_name, max_sites=0, max_benches=0, max_disk_gb=0,
                           allowed_site_types="", enabled_features="{}"):
    """Admin-only: create a new team + user directly."""
    _require_admin()

    if frappe.db.exists("User", email):
        frappe.throw(f"User {email} already exists.")

    user = frappe.get_doc({
        "doctype": "User",
        "email": email,
        "first_name": full_name.split()[0] if full_name else email.split("@")[0],
        "last_name": " ".join(full_name.split()[1:]) if len(full_name.split()) > 1 else "",
        "user_type": "Website User",
        "send_welcome_email": 0,
    }).insert(ignore_permissions=True)

    team = frappe.get_doc({
        "doctype": "Team",
        "user": email,
        "team_title": full_name,
        "enabled": 1,
        "max_sites": int(max_sites),
        "max_benches": int(max_benches),
        "max_disk_gb": float(max_disk_gb),
        "allowed_site_types": allowed_site_types,
        "enabled_features": enabled_features,
    })
    team.append("team_members", {"user": email})
    team.insert(ignore_permissions=True)
    frappe.db.commit()

    return {"team": team.name, "user": email}


def _server_admin_overrides(server_name):
    """Return (monthly_cost_override, is_decommissioned, admin_notes) for a server.
    Falls back to (0, 0, '') if Custom Fields not yet installed."""
    try:
        row = frappe.db.get_value(
            "Server", server_name,
            ["monthly_cost_override", "is_decommissioned", "admin_notes"],
            as_dict=True,
        )
        if not row:
            return 0, 0, ""
        return float(row.get("monthly_cost_override") or 0), int(row.get("is_decommissioned") or 0), row.get("admin_notes") or ""
    except Exception:
        return 0, 0, ""


def _effective_cost(server_name, baseline_cost):
    """Effective monthly cost: override if non-zero, else baseline."""
    override, _decom, _notes = _server_admin_overrides(server_name)
    return override if override > 0 else baseline_cost


def _calc_team_cost(team):
    """Calculate proportional infrastructure cost for a team. Skips decommissioned servers."""
    total = 0
    for server_name, info in SERVER_COSTS.items():
        _override, is_decom, _notes = _server_admin_overrides(server_name)
        if is_decom:
            continue
        server_sites = frappe.db.count("Site", {
            "server": server_name, "status": ("not in", ("Archived",)),
        })
        if server_sites == 0:
            continue
        team_sites = frappe.db.count("Site", {
            "team": team, "server": server_name, "status": ("not in", ("Archived",)),
        })
        if team_sites > 0:
            cost = _effective_cost(server_name, info["cost"])
            total += round(cost * team_sites / server_sites, 2)
    return round(total, 2)


def _get_server_costs():
    """Return server cost data with live site counts. Excludes decommissioned servers."""
    result = []
    for server_name, info in SERVER_COSTS.items():
        override, is_decom, _notes = _server_admin_overrides(server_name)
        if is_decom:
            continue
        sites = frappe.db.count("Site", {"server": server_name, "status": ("not in", ("Archived",))})
        teams = len(set(frappe.get_all("Site", {
            "server": server_name, "status": ("not in", ("Archived",)),
        }, pluck="team")))
        ip = frappe.db.get_value("Server", server_name, "ip") or ""
        result.append({
            "name": server_name,
            "ip": ip,
            "plan": info["plan"],
            "cost": override if override > 0 else info["cost"],
            "sites": sites,
            "teams": teams,
        })
    return result


@frappe.whitelist()
def get_servers_admin():
    """Return all servers (Server / Database Server / Proxy Server) with admin fields.
    Includes decommissioned servers — UI is responsible for visual treatment."""
    _require_admin()
    rows = []
    for kind, doctype in (("app", "Server"), ("db", "Database Server"), ("proxy", "Proxy Server")):
        try:
            servers = frappe.get_all(doctype, fields=["name", "ip", "status", "cluster", "creation"])
        except Exception:
            servers = []
        for s in servers:
            override, is_decom, notes = _server_admin_overrides(s["name"]) if kind == "app" else (0, 0, "")
            baseline_info = SERVER_COSTS.get(s["name"], {}) if kind == "app" else {}
            baseline_cost = baseline_info.get("cost", 0)
            plan = baseline_info.get("plan", "")
            sites = frappe.db.count("Site", {"server": s["name"], "status": ("not in", ("Archived",))}) if kind == "app" else 0
            benches = frappe.db.count("Bench", {"server": s["name"], "status": "Active"}) if kind == "app" else 0
            rows.append({
                "name": s["name"],
                "kind": kind,
                "ip": s.get("ip") or "",
                "status": s.get("status") or "",
                "cluster": s.get("cluster") or "",
                "plan": plan,
                "baseline_cost": baseline_cost,
                "monthly_cost_override": override,
                "effective_cost": override if override > 0 else baseline_cost,
                "is_decommissioned": is_decom,
                "admin_notes": notes,
                "sites": sites,
                "benches": benches,
            })
    return rows


@frappe.whitelist()
def update_server_admin(server, monthly_cost_override=None, admin_notes=None):
    """Edit admin-controlled fields on a Server. Custom fields only — no impact on Press lifecycle."""
    _require_admin()
    if not frappe.db.exists("Server", server):
        frappe.throw(f"Server {server} does not exist.")
    updates = {}
    if monthly_cost_override is not None:
        updates["monthly_cost_override"] = float(monthly_cost_override or 0)
    if admin_notes is not None:
        updates["admin_notes"] = admin_notes
    for field, value in updates.items():
        frappe.db.set_value("Server", server, field, value)
    frappe.db.commit()
    return {"ok": True, "updates": updates}


@frappe.whitelist()
def get_server_stats(server):
    """Return live RAM/CPU/disk stats for a server (cached 60s).
    Uses SSH from press-ctrl. Returns {error: 'ssh_failed'} on connectivity issues."""
    _require_admin()
    if not frappe.db.exists("Server", server):
        frappe.throw(f"Server {server} does not exist.")
    ip = frappe.db.get_value("Server", server, "ip") or ""
    from press.api.admin_panel_stats import collect_stats
    return collect_stats(server, ip)


@frappe.whitelist()
def set_server_decommissioned(server, decommissioned):
    """Toggle the soft-decommission flag on a Server. Excluded from cost rollups when true."""
    _require_admin()
    if not frappe.db.exists("Server", server):
        frappe.throw(f"Server {server} does not exist.")
    flag = 1 if str(decommissioned).lower() in ("1", "true", "yes") else 0
    frappe.db.set_value("Server", server, "is_decommissioned", flag)
    frappe.db.commit()
    return {"ok": True, "is_decommissioned": flag}
