"""Install is_decommissioned custom field on Database Server + Proxy
Server, then backfill from linked app Server's flag.

Why: the flag was previously only on tabServer. Crons that filtered
DB / Proxy Servers had to walk the link to check decom state, which
was error-prone and the source of the 2026-05-21 incident
(1798 wasted snapshot jobs against decommissioned test servers).

After this patch + the doc-event sync hook, decommissioning the app
Server propagates the flag to its DB + Proxy siblings automatically.
Future crons can filter directly with `is_decommissioned: 0`.
"""
import frappe

from press.press.doctype.database_server.database_server_admin_setup import (
    setup_database_server_admin_fields,
)
from press.press.doctype.proxy_server.proxy_server_admin_setup import (
    setup_proxy_server_admin_fields,
)


def execute():
    # Step 1: install the custom fields (idempotent)
    setup_database_server_admin_fields()
    setup_proxy_server_admin_fields()

    # Step 2: backfill is_decommissioned on Database Server from the linked
    # app Server's flag. A Database Server is "decommissioned" if it's
    # referenced as the .database_server on any decommissioned app Server.
    db_servers_to_flag = frappe.db.sql_list(
        """
        SELECT DISTINCT s.database_server
        FROM `tabServer` s
        WHERE s.is_decommissioned = 1
          AND s.database_server IS NOT NULL
          AND s.database_server != ''
        """
    )
    if db_servers_to_flag:
        frappe.db.sql(
            """
            UPDATE `tabDatabase Server`
            SET is_decommissioned = 1
            WHERE name IN %(names)s
            """,
            {"names": tuple(db_servers_to_flag)},
        )
        print(
            f"  Backfilled is_decommissioned=1 on {len(db_servers_to_flag)} "
            f"Database Server(s): {db_servers_to_flag}"
        )

    # Step 3: backfill on Proxy Server. A Proxy Server is "decommissioned"
    # only if ALL linked app Servers are decommissioned (a proxy can serve
    # multiple clusters).
    candidate_proxies = frappe.db.sql_list(
        """
        SELECT DISTINCT proxy_server FROM `tabServer`
        WHERE proxy_server IS NOT NULL AND proxy_server != ''
        """
    )
    proxies_to_flag = []
    for proxy in candidate_proxies:
        linked = frappe.db.sql(
            """
            SELECT is_decommissioned FROM `tabServer` WHERE proxy_server = %s
            """,
            (proxy,),
        )
        if linked and all(row[0] == 1 for row in linked):
            proxies_to_flag.append(proxy)
    if proxies_to_flag:
        frappe.db.sql(
            """
            UPDATE `tabProxy Server`
            SET is_decommissioned = 1
            WHERE name IN %(names)s
            """,
            {"names": tuple(proxies_to_flag)},
        )
        print(
            f"  Backfilled is_decommissioned=1 on {len(proxies_to_flag)} "
            f"Proxy Server(s): {proxies_to_flag}"
        )

    frappe.db.commit()
