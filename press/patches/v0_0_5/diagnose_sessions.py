import frappe

def execute():
    total = frappe.db.count('User', {'enabled': 1, 'name': ('!=', 'Guest')})
    by_type = frappe.db.sql("""SELECT user_type, COUNT(*) as cnt FROM tabUser WHERE enabled=1 AND name!='Guest' GROUP BY user_type""", as_dict=True)
    print('Total enabled non-Guest users:', total)
    for r in by_type:
        print(' ', r.user_type, ':', r.cnt)

    tms = frappe.db.sql("""SELECT u.name, u.user_type, u.simultaneous_sessions
        FROM tabUser u
        LEFT JOIN `tabTeam Member` tm ON tm.user=u.name
        WHERE u.enabled=1 AND u.name!='Guest' AND u.name!='Administrator' AND tm.name IS NOT NULL
        LIMIT 10""", as_dict=True)
    print('\nSample team members:')
    for t in tms:
        print(' ', t.name, 'type=', t.user_type, 'sim=', t.simultaneous_sessions)

    sessions = frappe.db.sql("""SELECT user, COUNT(*) as cnt FROM __Auth GROUP BY user ORDER BY cnt DESC LIMIT 10""", as_dict=True)
    print('\n__Auth table:')
    for s in sessions:
        print(' ', s.user, ':', s.cnt, 'sessions')
