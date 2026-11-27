"""How a Code Server archive ends when its bench may already be archived (0.7.79).

A Code Server runs inside its bench's container (the agent stops it with supervisorctl in that container), so when
the bench is archived the editor is already gone. The agent's "Archive Code Server" route checks that the bench
exists, so asking it after the bench is archived always fails and the Code Server used to end Broken, its name never
released. Since 0.7.78 a deploy archives the old bench's Code Server only after that bench is Archived, so this is
the normal path now. Once the bench is archived only the proxy upstream (and the DNS record) are left to remove.
"""

import frappe

UPSTREAM_JOB = "Remove Code Server from Upstream"
ARCHIVE_JOB = "Archive Code Server"


def bench_is_archived(bench_name: str | None) -> bool:
	if not bench_name:  # get_value with no name would read some other bench
		return False
	return frappe.db.get_value("Bench", bench_name, "status") == "Archived"


def archive_outcome(upstream: str | None, archive: str | None, bench_archived: bool) -> str:
	"""The Code Server's status from its two archive jobs. With the bench archived the editor went with it, so the
	archive job counts as done whether it was skipped or failed."""
	if bench_archived:
		archive = "Success"
	if upstream == archive == "Success":
		return "Archived"
	if "Failure" in (upstream, archive):
		return "Broken"
	return "Pending"


def latest_job_status(job_type: str, code_server: str) -> str | None:
	"""The newest job of that type, so a retried archive is not judged by an older failure."""
	return frappe.db.get_value(
		"Agent Job",
		{"job_type": job_type, "code_server": code_server},
		"status",
		order_by="creation desc",
		for_update=True,
	)
