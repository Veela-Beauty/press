import frappe
import json

def audit():
    suspects = [
        'f-0001.fc.dev', 'f-0002.fc.dev', 'f-0003.fc.dev', 'f-0004.fc.dev',
        'm2927.fc.dev', 'm2928.fc.dev', 'm2929.fc.dev', 'm2930.fc.dev',
        'n000001.fc.dev', 'n000002.fc.dev', 'n000003.fc.dev', 'n000004.fc.dev',
    ]
    linked_doctypes = ['Bench', 'Site', 'Agent Job', 'Site Backup']
    out = {}
    for s in suspects:
        server = frappe.db.get_value('Server', s, ['name','ip','status','cluster','plan','provider','is_managed'], as_dict=True)
        if not server:
            out[s] = {'exists': False}
            continue
        refs = {}
        for dt in linked_doctypes:
            try:
                cnt = frappe.db.count(dt, {'server': s})
                if cnt: refs[dt] = cnt
            except Exception as e:
                refs[dt] = f'err:{type(e).__name__}'
        out[s] = {
            'exists': True,
            'ip': server.ip,
            'status': server.status,
            'cluster': server.cluster,
            'plan': server.plan,
            'provider': server.provider,
            'is_managed': server.is_managed,
            'refs': refs,
        }
    return out

if __name__ == '__main__':
    import sys
    # When run via bench execute, frappe.init is done
    result = audit()
    print('AUDIT_RESULT_JSON:' + json.dumps(result, default=str))
