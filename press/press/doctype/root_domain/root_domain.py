# Copyright (c) 2021, Frappe and contributors
# For license information, please see license.txt
from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import frappe
import requests
from frappe.core.utils import find
from frappe.model.document import Document
from frappe.utils.caching import redis_cache

from press.utils import log_error

if TYPE_CHECKING:
	from press.press.doctype.proxy_server.proxy_server import ProxyServer


class RootDomain(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		cloudflare_api_token: DF.Password | None
		cloudflare_zone_id: DF.Data | None
		default_cluster: DF.Link
		default_proxy_server: DF.Link | None
		dns_provider: DF.Literal["Cloudflare", "AWS Route 53", "Generic"]
		enabled: DF.Check
		team: DF.Link | None
	# end: auto-generated types

	def after_insert(self):
		if self.dns_provider != "Generic" and not frappe.db.exists(
			"TLS Certificate", {"wildcard": True, "domain": self.name}
		):
			frappe.enqueue_doc(
				self.doctype,
				self.name,
				"obtain_root_domain_tls_certificate",
				enqueue_after_commit=True,
			)

	def obtain_root_domain_tls_certificate(self):
		try:
			rsa_key_size = frappe.db.get_value("Press Settings", "Press Settings", "rsa_key_size")
			frappe.get_doc(
				{
					"doctype": "TLS Certificate",
					"wildcard": True,
					"domain": self.name,
					"rsa_key_size": rsa_key_size,
					"provider": "Let's Encrypt",
				}
			).insert()
		except Exception:
			log_error("Root Domain TLS Certificate Exception")

	@property
	def generic_dns_provider(self):
		if not hasattr(self, "_generic_dns_provider"):
			self._generic_dns_provider = self.dns_provider == "Generic"

		return self._generic_dns_provider

	@property
	def cloudflare_headers(self):
		return {
			"Authorization": f"Bearer {self.get_password('cloudflare_api_token')}",
			"Content-Type": "application/json",
		}

	def get_dns_records(self, record_type=None, page=1, per_page=100):
		"""Fetch DNS records from Cloudflare API with pagination."""
		params = {"page": page, "per_page": per_page}
		if record_type:
			params["type"] = record_type
		try:
			resp = requests.get(
				f"https://api.cloudflare.com/client/v4/zones/{self.cloudflare_zone_id}/dns_records",
				headers=self.cloudflare_headers,
				params=params,
			)
			resp.raise_for_status()
			return resp.json().get("result", [])
		except Exception:
			log_error("Cloudflare DNS Pagination Error", domain=self.name)
		return []

	def get_all_dns_records(self, record_type=None):
		"""Fetch all DNS records with auto-pagination."""
		all_records = []
		page = 1
		while True:
			records = self.get_dns_records(record_type=record_type, page=page, per_page=100)
			if not records:
				break
			all_records.extend(records)
			if len(records) < 100:
				break
			page += 1
		return all_records

	def delete_dns_records(self, records: list[dict]):
		try:
			for record in records:
				record_id = record.get("id")
				if not record_id:
					continue
				requests.delete(
					f"https://api.cloudflare.com/client/v4/zones/{self.cloudflare_zone_id}/dns_records/{record_id}",
					headers=self.cloudflare_headers,
				).raise_for_status()
		except Exception:
			log_error("Cloudflare DNS Record Deletion Error", domain=self.name)

	def get_sites_being_renamed(self):
		# get sites renamed in Server but doc not renamed in press
		last_hour = datetime.now() - timedelta(hours=1)  # very large bound just to be safe
		renaming_sites = frappe.get_all(
			"Agent Job",
			{"job_type": "Rename Site", "creation": (">=", last_hour)},
			pluck="request_data",
		)
		return [json.loads(d_str)["new_name"] for d_str in renaming_sites]

	def get_active_site_domains(self):
		return frappe.get_all(
			"Site Domain", {"domain": ("like", f"%{self.name}"), "status": "Active"}, pluck="name"
		)

	def get_active_sites(self):
		return frappe.get_all("Site", {"status": ("!=", "Archived"), "domain": self.name}, pluck="name")

	def get_active_domains(self):
		active_domains = self.get_active_sites()
		active_domains.extend(self.get_sites_being_renamed())
		active_domains.extend(self.get_active_site_domains())
		return set(active_domains)

	def get_default_cluster_proxies(self):
		return frappe.get_all(
			"Proxy Server", {"status": "Active", "cluster": self.default_cluster}, pluck="name"
		)

	def remove_unused_cname_records(self):
		proxies = frappe.get_all("Proxy Server", {"status": "Active"}, pluck="name")
		default_proxies = self.get_default_cluster_proxies()

		cname_records = self.get_all_dns_records(record_type="CNAME")
		frappe.db.commit()
		active_domains = self.get_active_domains()

		to_delete = []
		for record in cname_records:
			value = record.get("content", "")
			if value in proxies:
				domain = record["name"]
				if domain not in active_domains:
					to_delete.append(record)
				elif value in default_proxies:
					to_delete.append(record)

		if to_delete:
			self.delete_dns_records(to_delete)

	def update_dns_records_for_sites(
		self, sites: list[str], proxy_server: str, batch_size: int = 500, ttl: int = 600
	):
		if self.generic_dns_provider:
			return

		headers = self.cloudflare_headers
		zone_id = self.cloudflare_zone_id

		for site in sites:
			payload = {"type": "CNAME", "name": site, "content": proxy_server, "ttl": ttl, "proxied": False}
			try:
				# Check if record exists
				resp = requests.get(
					f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records",
					headers=headers,
					params={"type": "CNAME", "name": site},
				)
				resp.raise_for_status()
				existing = resp.json().get("result", [])
				if existing:
					requests.put(
						f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records/{existing[0]['id']}",
						headers=headers,
						json=payload,
					).raise_for_status()
				else:
					requests.post(
						f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records",
						headers=headers,
						json=payload,
					).raise_for_status()
			except Exception:
				log_error("Cloudflare DNS Update Error", domain=self.name, site=site)

	@frappe.whitelist()
	def add_to_proxies(self):
		proxies = frappe.get_all("Proxy Server", {"status": "Active"}, pluck="name")
		for proxy_name in proxies:
			proxy: ProxyServer = frappe.get_doc("Proxy Server", proxy_name)
			proxy.append("domains", {"domain": self.name})
			proxy.save()
			proxy.setup_wildcard_hosts()


def cleanup_cname_records():
	domains = frappe.get_all("Root Domain", pluck="name")
	for domain_name in domains:
		domain = RootDomain("Root Domain", domain_name)
		if domain.generic_dns_provider:
			continue

		domain.remove_unused_cname_records()


@redis_cache(ttl=3600)
def get_domains():
	return frappe.get_all("Root Domain", filters={"enabled": ["=", "1"]}, pluck="name")


def get_matching_domain(domain: str) -> str | None:
	root_domains = get_domains()
	for rd in root_domains:
		if domain == rd or domain.endswith(f".{rd}"):
			return rd
	return None
