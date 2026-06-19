import frappe

def execute():
    print("=== All Users ===")
    for u in frappe.db.sql("""
        SELECT name, user_type, simultaneous_sessions
        FROM tabUser WHERE enabled=1 AND name!='Guest'
        ORDER BY user_type, name
    """, as_dict=True):
        print(f"  {u.name:40} type={u.user_type:15} sim={u.simultaneous_sessions}")

    print("\n=== Team Members ===")
    for tm in frappe.db.get_all("Team Member", fields=["name", "user"]):
        print(f"  TM={tm.name:20} user={tm.user}")

    print("\n=== Release Groups ===")
    for rg in frappe.db.get_all("Release Group", filters={"enabled": 1}, fields=["name", "team"]):
        print(f"  {rg.name:20} team={rg.team}")

    print("\n=== Recent Deploy Candidates ===")
    for dc in frappe.db.get_all("Deploy Candidate", fields=["name", "status", "group"], order_by="creation desc", limit=5):
        print(f"  {dc.name:30} status={dc.status:15} group={dc.group}")

    print("\n=== Press Settings ===")
    ps = frappe.get_single("Press Settings")
    print(f"  use_naming_series: {ps.use_naming_series}")

    # Check what happens when a Website User hits deploy_and_update
    print("\n=== Testing @protected for Release Group ===")
    from press.api.site import protected
    import inspect
    print(f"  protected source file: {inspect.getfile(protected)}")

    # Simulate what deploy_and_update checks
    print("\n=== deploy_and_update check ===")
    from press.api.bench import deploy_and_update as _
    import inspect as ins
    src = ins.getsource(_)
    print(src[:500])
