import re
import frappe
from frappe import _

from press.press.doctype.bench.bench_dev_overview import _ensure_team_access


@frappe.whitelist()
def get_vscode_remote_url(bench_name: str) -> str:
	"""
	Return a `vscode://vscode-remote/ssh-remote+<bench>@<proxy>:2222/home/frappe/frappe-bench`
	URL for launching local VS Code Desktop against a Press-managed bench over SSH.

	Port 2222 is the user-facing SSH proxy port (cert-based, matches SSHCertificateDialog).
	Distinct from the 22000+offset admin port used for direct bench-server SSH.

	Permission: caller must have read access to the Bench (frappe.get_doc enforces this).
	Plus team-membership via _ensure_team_access for parity with sibling APIs.
	"""
	_ensure_team_access(bench_name=bench_name)
	bench = frappe.get_doc("Bench", bench_name)
	if not re.fullmatch(r"[a-zA-Z0-9_.-]+", bench.name):
		frappe.throw(_("Bench name {0} is not safe for URI composition.").format(bench.name))
	proxy_server = frappe.db.get_value("Server", bench.server, "proxy_server")
	if not proxy_server:
		frappe.throw(
			_("This bench has no proxy server configured. Run Generate SSH Certificate first.")
		)
	return (
		f"vscode://vscode-remote/ssh-remote+{bench.name}@{proxy_server}:2222"
		f"/home/frappe/frappe-bench"
	)
