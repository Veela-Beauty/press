# Copyright (c) 2024, Frappe and contributors
# For license information, please see license.txt

from datetime import datetime
from typing import Optional, TypedDict

import frappe
from frappe.model.document import Document

ExecuteResult = TypedDict(
	"ExecuteResult",
	{
		"command": str,
		"status": str,
		"start": str,
		"end": str,
		"duration": float,
		"output": str,
		"directory": Optional[str],
		"traceback": Optional[str],
		"returncode": Optional[int],
	},
)


class BenchShellLog(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		bench: DF.Link | None
		cmd: DF.Code | None
		directory: DF.Data | None
		duration: DF.Float
		end: DF.Datetime | None
		output: DF.Code | None
		returncode: DF.Int
		start: DF.Datetime | None
		status: DF.Data | None
		subdir: DF.Data | None
		traceback: DF.Code | None
	# end: auto-generated types


def create_bench_shell_log(
	res: "ExecuteResult",
	bench: str,
	cmd: str,
	subdir: Optional[str],
	save_output: bool,
) -> None:
	doc_dict = {
		"doctype": "Bench Shell Log",
		"cmd": cmd,
		"bench": bench,
		"subdir": subdir,
		**res,
	}
	doc_dict["start"] = datetime.fromisoformat(res["start"])
	doc_dict["end"] = datetime.fromisoformat(res["end"])
	if not save_output:
		del doc_dict["output"]
	# Bench Shell Log doctype grants create perm only to System Manager. Any
	# user-facing dashboard flow that hits Bench.docker_execute (bench dev
	# watch, bench dev overview's run_python_on_site / run_sql_on_site,
	# app management's create_app_locally, etc.) needs to write here for
	# audit purposes — but team users don't carry the System Manager role.
	# Bypass perms on insert: the `owner` field still captures who triggered
	# the shell, so the audit trail stays intact. Without this bypass, every
	# such dashboard action throws "No permission for Bench Shell Log" for
	# non-System users. Reported 2026-05-19 by ahmedmowafy74@gmail.com
	# whose bench Actions page flooded with the error every 10s via the
	# Bench Watch poll.
	frappe.get_doc(doc_dict).insert(ignore_permissions=True)
	frappe.db.commit()
