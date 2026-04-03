import frappe
import json

def dump():
    frappe.set_user("Administrator")
    config = {}

    # 1. Press Settings
    ps = frappe.get_doc("Press Settings")
    config["press_settings"] = {
        "domain": ps.domain,
        "cluster": ps.cluster,
        "docker_registry_url": ps.docker_registry_url,
        "build_server": ps.build_server,
        "clone_directory": ps.clone_directory,
        "build_directory": ps.build_directory,
        "bench_configuration": ps.bench_configuration,
        "free_credits_usd": float(ps.free_credits_usd or 0),
        "backup_interval": ps.backup_interval,
        "backup_limit": ps.backup_limit,
        "disable_physical_backup": ps.disable_physical_backup,
        "offsite_backups_count": ps.offsite_backups_count,
        "use_asset_store": ps.use_asset_store,
        "suspend_builds": ps.suspend_builds,
        "minimum_rebuild_memory": ps.minimum_rebuild_memory,
        "use_agent_job_callbacks": ps.use_agent_job_callbacks,
        "send_telegram_notifications": ps.send_telegram_notifications,
        "send_email_notifications": ps.send_email_notifications,
        "certbot_directory": ps.certbot_directory,
        "eff_registration_email": ps.eff_registration_email,
        "rsa_key_size": ps.rsa_key_size,
        "agent_repository_owner": ps.agent_repository_owner,
        "branch": ps.branch,
        "github_app_id": ps.github_app_id,
        "github_app_client_id": ps.github_app_client_id,
        "github_app_public_link": ps.github_app_public_link,
        # Secrets marked as PLACEHOLDER
        "github_app_client_secret": "REPLACE_WITH_SECRET",
        "github_app_private_key": "REPLACE_WITH_PEM",
    }

    # Default apps
    config["default_apps"] = []
    for a in ps.default_apps:
        d = a.as_dict()
        config["default_apps"].append({k: v for k, v in d.items() if k not in ["name", "parent", "parenttype", "parentfield", "doctype", "idx", "owner", "creation", "modified", "modified_by", "docstatus"]})

    # ERPNext apps
    config["erpnext_apps"] = []
    for a in ps.erpnext_apps:
        d = a.as_dict()
        config["erpnext_apps"].append({k: v for k, v in d.items() if k not in ["name", "parent", "parenttype", "parentfield", "doctype", "idx", "owner", "creation", "modified", "modified_by", "docstatus"]})

    # 2. Cluster
    clusters = frappe.get_all("Cluster", fields=["name", "title", "image", "public", "beta"])
    config["clusters"] = clusters

    # 3. Frappe Versions
    versions = frappe.get_all("Frappe Version", fields=["name", "status", "number", "public", "default"])
    config["frappe_versions"] = versions

    # 4. Apps
    apps = frappe.get_all("App", fields=["name", "title", "frappe"])
    config["apps"] = apps

    # 5. App Sources
    sources = frappe.get_all("App Source", fields=[
        "name", "app", "app_title", "repository_url", "branch",
        "team", "public", "enabled", "frappe"
    ])
    for s in sources:
        versions = frappe.get_all("App Source Version",
            filters={"parent": s.name},
            fields=["version"])
        s["versions"] = [v.version for v in versions]
    config["app_sources"] = sources

    # 6. Marketplace Apps
    mp_apps = frappe.get_all("Marketplace App", fields=[
        "name", "app", "title", "frappe_approved", "status", "image"
    ])
    config["marketplace_apps"] = mp_apps

    # 7. Site Plans
    plans = frappe.get_all("Site Plan", fields=[
        "name", "plan_title", "price_usd", "price_inr",
        "cpu_time_per_day", "max_storage_usage",
        "max_database_usage", "database_access", "support_included"
    ])
    config["site_plans"] = plans

    # 8. Teams
    teams = frappe.get_all("Team", fields=[
        "name", "user", "enabled", "free_account",
        "servers_enabled", "billing_team"
    ])
    config["teams"] = teams

    # 9. Server records
    servers = frappe.get_all("Server", fields=[
        "name", "status", "cluster", "team",
        "use_for_new_benches", "use_for_new_sites", "use_for_build",
        "proxy_server", "database_server"
    ])
    config["servers"] = servers

    db_servers = frappe.get_all("Database Server", fields=[
        "name", "status", "cluster", "team"
    ])
    config["database_servers"] = db_servers

    proxy_servers = frappe.get_all("Proxy Server", fields=[
        "name", "status", "cluster", "team"
    ])
    config["proxy_servers"] = proxy_servers

    # 10. Release Groups
    rgs = frappe.get_all("Release Group", fields=[
        "name", "title", "version", "team", "enabled"
    ])
    for rg in rgs:
        rg_doc = frappe.get_doc("Release Group", rg.name)
        rg["apps"] = [{"app": a.app, "source": a.source} for a in rg_doc.apps]
        rg["servers"] = [{"server": s.server} for s in rg_doc.servers]
    config["release_groups"] = rgs

    # 11. Root Domain
    rd = frappe.get_all("Root Domain", fields=["name", "dns_provider", "default_cluster"])
    config["root_domains"] = rd

    # Convert to JSON
    output = json.dumps(config, indent=2, default=str)
    print(output)
