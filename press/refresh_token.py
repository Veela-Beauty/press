import frappe
import requests

def refresh():
    frappe.set_user("Administrator")
    team = "sqkn1globp"

    # Check current token
    token = frappe.db.get_value("Team", team, "github_access_token")
    print(f"Current token: {'SET' if token else 'NOT SET'}")

    # Test if token works
    if token:
        resp = requests.get("https://api.github.com/user", headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        })
        print(f"Token test: {resp.status_code}")
        if resp.status_code != 200:
            print(f"Token expired or invalid: {resp.json().get('message', '')}")
            token = None

    if not token:
        # Refresh using JWT
        from press.api.github import get_jwt_token
        jwt_token = get_jwt_token()
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Accept": "application/vnd.github.v3+json",
        }
        resp = requests.get("https://api.github.com/app/installations", headers=headers)
        if resp.status_code == 200 and resp.json():
            inst_id = resp.json()[0]["id"]
            token_resp = requests.post(
                f"https://api.github.com/app/installations/{inst_id}/access_tokens",
                headers=headers,
            )
            if token_resp.status_code == 201:
                new_token = token_resp.json()["token"]
                frappe.db.set_value("Team", team, "github_access_token", new_token)
                frappe.db.commit()
                print(f"Token refreshed!")
                token = new_token

    # Now test the github options API
    frappe.set_user("test@mvpstorm.com")
    from press.api.github import options
    result = options()
    print(f"\nGitHub options:")
    print(f"  authorized: {result.get('authorized')}")
    print(f"  installation_url: {result.get('installation_url')}")
    print(f"  installations: {len(result.get('installations', []))}")
    for inst in result.get("installations", []):
        print(f"    {inst.get('login')}: {len(inst.get('repos', []))} repos")
        for repo in inst.get("repos", [])[:5]:
            print(f"      - {repo.get('name')}")
