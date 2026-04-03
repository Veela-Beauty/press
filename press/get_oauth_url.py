import frappe
import json
from base64 import b64encode

def get_url():
    frappe.set_user("Administrator")
    client_id = frappe.db.get_single_value("Press Settings", "github_app_client_id")
    team = "sqkn1globp"
    state = b64encode(json.dumps({
        "team": team,
        "url": "https://demo.mvpstorm.com/dashboard/groups/bench-0003/apps"
    }).encode()).decode()

    oauth_url = f"https://github.com/login/oauth/authorize?client_id={client_id}&state={state}"
    print(f"\nOpen this URL in your browser to authorize:")
    print(oauth_url)
    print(f"\nThis will redirect to /github/authorize with the OAuth code.")
