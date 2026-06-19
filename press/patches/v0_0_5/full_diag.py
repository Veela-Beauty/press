import frappe

def execute():
    print("=== User Type Distribution ===")
    for r in frappe.db.sql("""
        SELECT user_type, COUNT(*) as cnt
        FROM tabUser WHERE enabled=1 AND name!='Guest'
        GROUP BY user_type
    """, as_dict=True):
        print(f"  {r.user_type}: {r.cnt}")

    print("\n=== All Users (non-Guest) ===")
    for u in frappe.db.sql("""
        SELECT name, user_type, simultaneous_sessions
        FROM tabUser WHERE enabled=1 AND name!='Guest'
        ORDER BY user_type, name
    """, as_dict=True):
        print(f"  {u.name:40} type={u.user_type:15} sim={u.simultaneous_sessions}")

    print("\n=== Team Members ===")
    for tm in frappe.db.sql("""
        SELECT tm.name, tm.user, tm.team, u.user_type
        FROM `tabTeam Member` tm
        JOIN tabUser u ON u.name=tm.user
        WHERE u.enabled=1
    """, as_dict=True):
        print(f"  TM={tm.name:20} user={tm.user:35} team={tm.team:20} type={tm.user_type}")

    print("\n=== Release Groups ===")
    for rg in frappe.db.sql("""
        SELECT name, team, enabled
        FROM `tabRelease Group`
        WHERE enabled=1
    """, as_dict=True):
        print(f"  {rg.name:20} team={rg.team:20} enabled={rg.enabled}")

    print("\n=== Recent Deploy Candidates ===")
    for dc in frappe.db.sql("""
        SELECT name, status, group_name, creation
        FROM `tabDeploy Candidate`
        ORDER BY creation DESC LIMIT 5
    """, as_dict=True):
        print(f"  {dc.name:30} status={dc.status:15} group={dc.group_name:20} created={dc.creation}")

    # Gunicorn worker check
    print("\n=== Gunicorn Settings ===")
    import os
    print(f"  GUNICORN_WORKERS from env: {os.environ.get('GUNICORN_WORKERS', 'not set')}")
    print(f"  WEB_WORKERS from env: {os.environ.get('WEB_WORKERS', 'not set')}")
    print(f"  SERVER_ROLE from env: {os.environ.get('SERVER_ROLE', 'not set')}")
