import frappe

def check():
    frappe.set_user("Administrator")
    
    # Check all teams
    teams = frappe.get_all("Team", fields=["name", "user", "enabled"])
    print("Teams:")
    for t in teams:
        print(f"  {t.name}: user={t.user} enabled={t.enabled}")
    
    # Check Release Groups and their teams
    rgs = frappe.get_all("Release Group", fields=["name", "title", "team", "enabled", "version"])
    print(f"\nRelease Groups:")
    for r in rgs:
        print(f"  {r.name}: {r.title} team={r.team} enabled={r.enabled} version={r.version}")
    
    # Check Marketplace App availability
    mp = frappe.get_all("Marketplace App", fields=["name", "app", "title"], limit=10)
    print(f"\nMarketplace Apps: {len(mp)}")
    for m in mp:
        print(f"  {m.name}: {m.app} - {m.title}")
    
    # Check Press Settings relevant fields
    ps = frappe.get_doc("Press Settings")
    print(f"\nPress Settings:")
    print(f"  domain: {ps.domain}")
    print(f"  build_server: {getattr(ps, build_server, N/A)}")
    print(f"  clone_directory: {getattr(ps, clone_directory, N/A)}")
    print(f"  build_directory: {getattr(ps, build_directory, N/A)}")
    
    # Check what user is logged into dashboard
    # The dashboard uses Website Users typically
    website_users = frappe.get_all("User", filters={"user_type": "Website User"}, fields=["name", "enabled"])
    print(f"\nWebsite Users:")
    for u in website_users:
        print(f"  {u.name}: enabled={u.enabled}")

