def audit():
    """Count Delivery Failure jobs to decommissioned f-000* benches in last 24h.
    These are the noise problem #2 — figure out who's creating them."""
    import frappe
    rows = frappe.db.sql(
        """SELECT job_type, bench, status, COUNT(*) AS n,
                  MIN(creation) AS oldest, MAX(creation) AS newest
           FROM `tabAgent Job`
           WHERE bench LIKE 'bench-002%-press-f1' OR bench LIKE '%-f-000%'
             AND creation > NOW() - INTERVAL 24 HOUR
             AND status IN ('Delivery Failure','Failure','Undelivered','Pending')
           GROUP BY job_type, bench, status
           ORDER BY n DESC LIMIT 20""",
        as_dict=True,
    )
    print(f"DECOM-CLUSTER FAILED/PENDING JOBS in last 24h: {len(rows)} groups")
    for r in rows:
        print(f"  {r.n:>4}x  {r.job_type:<28}  {r.bench:<40}  {r.status}  oldest={r.oldest}")

    # Are the underlying servers/benches still Active in the DB?
    print()
    print("BENCHES for the f-000* test cluster:")
    benches = frappe.db.sql(
        """SELECT name, status, group, server, creation
           FROM `tabBench`
           WHERE name LIKE 'bench-002%-f-000%'
           ORDER BY creation DESC LIMIT 10""",
        as_dict=True,
    )
    for b in benches:
        print(f"  {b.name}  status={b.status}  rg={b.group}  server={b.server}")

    print()
    print("SERVERS for f-000* cluster:")
    servers = frappe.db.sql(
        """SELECT name, status, is_decommissioned, ip
           FROM `tabServer`
           WHERE name LIKE 'f-000%' OR name LIKE 'm29%' OR name LIKE 'n0%'
           ORDER BY name""",
        as_dict=True,
    )
    for s in servers:
        print(f"  {s.name:<30}  status={s.status:<10}  decom={s.is_decommissioned}  ip={s.ip}")
