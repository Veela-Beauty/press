"""
Create a fresh Frappe app, push to GitHub, and register in Press.
Keeps press/api/marketplace.py untouched (upstream code).
"""

import os
import shutil
import subprocess
import tempfile

import frappe
import requests

from press.utils import get_current_team


SCAFFOLD_FILES = {
    "setup.py": """from setuptools import setup, find_packages

setup(
    name="{app_name}",
    version="0.0.1",
    author="{team}",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=["frappe"],
)
""",
    "{app_name}/__init__.py": "",
    "{app_name}/hooks.py": """app_name = "{app_name}"
app_title = "{app_title}"
app_publisher = "{team}"
app_description = "{description}"
app_email = ""
app_license = "MIT"
""",
    "{app_name}/modules.txt": "{module_name}",
    "{app_name}/{module_name}/__init__.py": "",
    "pyproject.toml": """[project]
name = "{app_name}"
version = "0.0.1"
requires-python = ">=3.10"

[build-system]
requires = ["flit_core >=3.4,<4"]
build-backend = "flit_core.buildapi"

[tool.bench.frappe-dependencies]
frappe = ">=15.0.0"
""",
    ".gitignore": """__pycache__/
*.pyc
*.egg-info
node_modules/
.DS_Store
*.sql.gz
*.sql
*.tar
""",
    "README.md": "# {app_title}\n\n{description}\n",
    "license.txt": "MIT License\n",
}


def _get_token_for_team() -> str:
    """Get GitHub token: team-level first, then global fallback."""
    team = get_current_team()
    # 1. Check team's own OAuth token
    team_token = frappe.db.get_value("Team", team, "github_access_token")
    if team_token:
        return team_token

    # 2. Fallback to global token (self-hosted instance — all teams trusted)
    global_token = frappe.db.get_single_value("Press Settings", "github_access_token")
    if global_token:
        return global_token

    frappe.throw("No GitHub connection configured. Contact your administrator.")


def _get_headers(token: str) -> dict:
    return {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}


@frappe.whitelist()
def get_github_owners() -> list[dict]:
    """Return list of GitHub accounts the current team can push to."""
    token = _get_token_for_team()
    headers = _get_headers(token)
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


@frappe.whitelist()
def create_app(
    app_name: str, app_title: str, github_owner: str = "",
    description: str = "", bench_group: str = "",
) -> dict:
    """Create a fresh Frappe app scaffold, push to GitHub, register in Press."""
    token = _get_token_for_team()
    headers = _get_headers(token)
    team = get_current_team()

    if not description:
        description = app_title

    # Validate app name
    app_name = app_name.strip().lower().replace("-", "_").replace(" ", "_")
    if not app_name.isidentifier():
        frappe.throw(f"Invalid app name: {app_name}. Use lowercase letters, numbers, and underscores.")
    if frappe.db.exists("App", app_name):
        frappe.throw(f"App '{app_name}' already exists in Press.")

    # Module name = valid Python identifier
    module_name = app_title.strip().replace(" ", "_").replace("-", "_")

    # Detect the authenticated GitHub user
    github_user = ""
    user_resp = requests.get("https://api.github.com/user", headers=headers, timeout=10)
    if user_resp.ok:
        github_user = user_resp.json().get("login", "")
    if not github_owner:
        github_owner = github_user

    # Detect Frappe version from bench
    frappe_version = "Version 15"
    if bench_group:
        version = frappe.db.get_value("Release Group", bench_group, "version")
        if version:
            frappe_version = version

    # 1. Create GitHub repo (user vs org)
    is_org = github_owner != github_user
    _create_github_repo(app_name, description, github_owner, headers, is_org)

    # 2. Scaffold and push
    try:
        _scaffold_and_push(app_name, app_title, module_name, description, team, github_owner, token)
    except Exception:
        _delete_github_repo(github_owner, app_name, headers)
        raise

    # 3. Register in Press
    app_doc = frappe.get_doc({"doctype": "App", "name": app_name, "title": app_title})
    app_doc.insert()

    source = app_doc.add_source(
        frappe_version=frappe_version,
        repository_url=f"https://github.com/{github_owner}/{app_name}",
        branch="main",
        team=team,
    )

    # 4. Create initial App Release
    try:
        source.create_release()
    except Exception:
        frappe.log_error("Failed to create initial release for new app")

    # 5. Auto-add to bench
    added_to_bench = False
    if bench_group:
        try:
            rg = frappe.get_doc("Release Group", bench_group)
            rg.add_app({"app": app_name, "source": source.name})
            added_to_bench = True
        except Exception as e:
            frappe.log_error(f"Failed to auto-add app to bench: {e}")

    frappe.db.commit()

    return {
        "app": app_doc.name,
        "source": source.name,
        "repository_url": f"https://github.com/{github_owner}/{app_name}",
        "added_to_bench": added_to_bench,
    }


def _create_github_repo(app_name: str, description: str, owner: str, headers: dict, is_org: bool):
    """Create a GitHub repository."""
    url = f"https://api.github.com/orgs/{owner}/repos" if is_org else "https://api.github.com/user/repos"
    resp = requests.post(
        url, headers=headers,
        json={"name": app_name, "description": description, "private": False, "auto_init": False},
        timeout=30,
    )
    if resp.status_code == 201:
        return
    elif resp.status_code == 422 and "already exists" in resp.text:
        frappe.throw(f"GitHub repo '{owner}/{app_name}' already exists.")
    else:
        frappe.throw(f"Failed to create GitHub repo: {resp.json().get('message', resp.text[:200])}")


def _delete_github_repo(owner: str, app_name: str, headers: dict):
    """Best-effort cleanup on rollback."""
    try:
        requests.delete(f"https://api.github.com/repos/{owner}/{app_name}", headers=headers, timeout=10)
    except Exception:
        pass


def _scaffold_and_push(
    app_name: str, app_title: str, module_name: str,
    description: str, team: str, owner: str, token: str,
):
    """Create app scaffold in temp dir and push to GitHub."""
    tmpdir = tempfile.mkdtemp(prefix=f"press-new-app-{app_name}-")
    try:
        for path_tpl, content_tpl in SCAFFOLD_FILES.items():
            path = os.path.join(tmpdir, path_tpl.format(app_name=app_name, module_name=module_name))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                f.write(content_tpl.format(
                    app_name=app_name, app_title=app_title,
                    module_name=module_name, description=description, team=team,
                ))

        push_url = f"https://{token}@github.com/{owner}/{app_name}.git"
        env = {
            **os.environ,
            "GIT_AUTHOR_NAME": "Press", "GIT_COMMITTER_NAME": "Press",
            "GIT_AUTHOR_EMAIL": "noreply@press.local", "GIT_COMMITTER_EMAIL": "noreply@press.local",
        }
        for cmd in [
            ["git", "init"],
            ["git", "checkout", "-b", "main"],
            ["git", "add", "."],
            ["git", "commit", "-m", f"feat: scaffold {app_title} app"],
            ["git", "remote", "add", "origin", push_url],
            ["git", "push", "-u", "origin", "main"],
        ]:
            result = subprocess.run(cmd, cwd=tmpdir, capture_output=True, text=True, timeout=60, env=env)
            if result.returncode != 0:
                stderr = result.stderr.replace(token, "***")
                frappe.throw(f"Git failed: {' '.join(cmd[:3])}\n{stderr[:200]}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
