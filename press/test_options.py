import frappe

def test():
    frappe.set_user("test@mvpstorm.com")
    from press.api.bench import options
    result = options()
    versions = result.get("versions", [])
    clusters = result.get("clusters", [])
    print(f"Versions: {len(versions)}")
    for v in versions:
        apps = v.get("apps", [])
        print(f"  {v[chr(110)+chr(97)+chr(109)+chr(101)]}: {v.get(chr(115)+chr(116)+chr(97)+chr(116)+chr(117)+chr(115))} - {len(apps)} apps")
        for a in apps:
            print(f"    {a[chr(110)+chr(97)+chr(109)+chr(101)]}: {a.get(chr(116)+chr(105)+chr(116)+chr(108)+chr(101))}")
    print(f"\nClusters: {len(clusters)}")
    for c in clusters:
        print(f"  {c}")
