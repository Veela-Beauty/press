import frappe
import requests

def fix():
    frappe.set_user("Administrator")

    # Check team's github access token
    team = "sqkn1globp"
    token = frappe.db.get_value("Team", team, "github_access_token")
    print(f"Team {team} github_access_token: {'SET' if token else 'NOT SET'}")

    # The OAuth flow didn't complete. We need to get a token via the GitHub App installation.
    # Since the app is installed, we can use the App's private key to get an installation token.

    from press.api.github import get_jwt_token, fetch_installations

    # Get JWT token from the app private key
    jwt_token = get_jwt_token()
    print(f"JWT token: {'OK' if jwt_token else 'FAILED'}")

    # Get installations
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Accept": "application/vnd.github.v3+json",
    }
    resp = requests.get("https://api.github.com/app/installations", headers=headers)
    print(f"Installations API: {resp.status_code}")

    if resp.status_code == 200:
        installs = resp.json()
        print(f"Found {len(installs)} installations")
        for inst in installs:
            print(f"  ID: {inst['id']} Account: {inst['account']['login']}")

            # Get installation access token
            token_resp = requests.post(
                f"https://api.github.com/app/installations/{inst['id']}/access_tokens",
                headers=headers,
            )
            if token_resp.status_code == 201:
                install_token = token_resp.json()["token"]
                print(f"  Installation token: OK")

                # Save to team
                frappe.db.set_value("Team", team, "github_access_token", install_token)
                frappe.db.commit()
                print(f"  Saved token to team {team}")
            else:
                print(f"  Token error: {token_resp.status_code} {token_resp.text[:200]}")
    else:
        print(f"Error: {resp.text[:500]}")
