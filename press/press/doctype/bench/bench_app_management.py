"""
Local app creation and GitHub push for benches.
Runs commands inside bench Docker containers via docker_execute().
"""

import frappe
import requests

from press.press.doctype.bench.bench_dev_overview import get_bench_app_names
from press.utils import get_current_team



def _ensure_team_access(bench_name=None, site_name=None):
	"""Allow System Managers, or team members/owner of the bench/site team."""
	if frappe.session.data and frappe.session.data.user_type == "System User":
		return
	if "System Manager" in frappe.get_roles(frappe.session.user):
		return
	from press.utils import get_current_team
	current_team = get_current_team()
	target_team = None
	if bench_name:
		target_team = frappe.db.get_value("Bench", bench_name, "team") or \
			frappe.db.get_value("Release Group", frappe.db.get_value("Bench", bench_name, "group"), "team")
	elif site_name:
		target_team = frappe.db.get_value("Site", site_name, "team")
	if not target_team or target_team != current_team:
		frappe.throw("Not allowed", frappe.PermissionError)


@frappe.whitelist()
def create_app_locally(bench_name, app_name, app_title):
	"""
	Create a new Frappe app inside the bench container via bench new-app.
	The app is created locally — no GitHub push. Push later from Dev tab.
	"""
	_ensure_team_access(bench_name=bench_name)

	app_name = app_name.strip().lower().replace("-", "_").replace(" ", "_")
	if not app_name.isidentifier():
		frappe.throw(f"Invalid app name: {app_name}. Use lowercase letters, numbers, and underscores.")

	bench = frappe.get_doc("Bench", bench_name)

	existing = get_bench_app_names(bench_name)
	if app_name in existing:
		frappe.throw(f"App '{app_name}' already exists in this bench.")

	safe_title = app_title.replace("'", "")
	cmd = (
		f"bash -c \""
		f"echo -e '{safe_title}\\n{safe_title}\\n\\n\\nMIT' "
		f"| bench new-app --no-git {app_name} "
		f"&& cd apps/{app_name} "
		f"&& git init && git checkout -b main && git add -A "
		f'&& git commit -m \\"feat: scaffold {safe_title} app\\""'
	)

	result = bench.docker_execute(cmd)

	if result.get("output") and "Error" not in result.get("output", ""):
		sites = frappe.get_all(
			"Site", {"bench": bench_name, "status": "Active"}, pluck="name", limit=1,
		)
		if sites:
			bench.docker_execute(f"bash -c 'bench --site {sites[0]} install-app {app_name}'")

	return result


@frappe.whitelist()
def init_github_for_app(bench_name, app_name, github_owner, repo_name=""):
	"""
	Initialize a GitHub repo for a locally-created app and push.
	Called from Dev tab when developer is ready to push.
	"""
	_ensure_team_access(bench_name=bench_name)

	bench = frappe.get_doc("Bench", bench_name)
	if not repo_name:
		repo_name = app_name

	token = _get_github_token()
	headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}

	github_user = _get_github_user(headers)
	is_org = github_owner != github_user

	# Create GitHub repo
	url = f"https://api.github.com/orgs/{github_owner}/repos" if is_org else "https://api.github.com/user/repos"
	resp = requests.post(url, headers=headers, json={"name": repo_name, "private": False}, timeout=30)
	if resp.status_code == 422 and "already exists" in resp.text:
		pass  # Repo exists — just push
	elif resp.status_code != 201:
		frappe.throw(f"Failed to create repo: {resp.json().get('message', resp.text[:200])}")

	# Add remote and push inside container
	push_url = f"https://{token}@github.com/{github_owner}/{repo_name}.git"
	cmd = (
		f"bash -c 'cd apps/{app_name} && "
		f"git remote remove origin 2>/dev/null; "
		f"git remote add origin {push_url} "
		f"&& git push -u origin main'"
	)
	result = bench.docker_execute(cmd)

	# Register in Press
	repo_url = f"https://github.com/{github_owner}/{repo_name}"
	_register_app_in_press(app_name, repo_url, token, headers)

	return {"repository_url": repo_url, "push_result": result}


@frappe.whitelist()
def get_github_accounts():
	"""Return GitHub accounts (user + orgs) available for the current team."""
	token = _get_github_token()
	headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
	owners = []

	user_resp = requests.get("https://api.github.com/user", headers=headers, timeout=10)
	if user_resp.ok:
		u = user_resp.json()
		owners.append({"login": u["login"], "type": "User", "avatar": u.get("avatar_url", "")})

	orgs_resp = requests.get("https://api.github.com/user/orgs", headers=headers, timeout=10)
	if orgs_resp.ok:
		for o in orgs_resp.json():
			owners.append({"login": o["login"], "type": "Organization", "avatar": o.get("avatar_url", "")})

	return owners


def _get_github_token() -> str:
	team = get_current_team()
	token = frappe.db.get_value("Team", team, "github_access_token")
	if not token:
		token = frappe.db.get_single_value("Press Settings", "github_access_token")
	if not token:
		frappe.throw("No GitHub token configured. Contact your administrator.")
	return token


def _get_github_user(headers: dict) -> str:
	resp = requests.get("https://api.github.com/user", headers=headers, timeout=10)
	return resp.json().get("login", "") if resp.ok else ""


def _register_app_in_press(app_name: str, repo_url: str, token: str, headers: dict):
	team = get_current_team()

	if not frappe.db.exists("App", app_name):
		from press.press.doctype.app.app import new_app
		new_app(app_name, app_name)

	app_doc = frappe.get_doc("App", app_name)
	source = app_doc.add_source(
		frappe_version="Version 15",
		repository_url=repo_url,
		branch="main",
		team=team,
	)
	try:
		source.create_release()
	except Exception:
		pass

	frappe.db.commit()
