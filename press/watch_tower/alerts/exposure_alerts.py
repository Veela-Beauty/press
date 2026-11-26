"""Exposure watch: service ports open to the internet, public API route lists, routes that answer without a key, and
Sanad Preview's login.

Looked at from outside, hourly: press-ctrl probes the other servers, and accubuild-stg (the one server press-ctrl
reaches over SSH) probes press-ctrl. Read-only: TCP connects and HTTP GETs; nothing that runs is ever sent.
26 Nov 2026: code-analysis had port 8200 open to the internet on press-ctrl, Sanad Brain answered /admin/audit
without a key, and its /openapi.json listed every route.

No frappe import at module level, so the probe logic loads and tests without a bench.
"""

import concurrent.futures
import re
import socket
import ssl
import urllib.error
import urllib.request

SERVERS = {"press-ctrl": "89.167.116.92", "sandbox-1": "65.108.128.91", "hetzner-main": "65.109.65.159"}
PRESS_CTRL_VANTAGE = "89.167.57.21"  # accubuild-stg
# Ports our containers use; open from the internet they skip Traefik and its logins (Docker ports bypass ufw).
SERVICE_PORTS = (
	2375,
	3000,
	3001,
	3100,
	3306,
	4000,
	4100,
	5000,
	5432,
	5672,
	6333,
	6379,
	7474,
	7687,
	8000,
	8080,
	8081,
	8090,
	8200,
	8443,
	8710,
	8880,
	9000,
	9090,
	9100,
	9200,
	9300,
	11434,
	15672,
	27017,
)
# press-ctrl's registry: its DOCKER-USER rule lets only the build servers in, and accubuild-stg is one of them.
ALLOWED_PORTS = {("press-ctrl", 5000)}

PREVIEW = "https://sanad-preview.sanadeoi.mvpstorm.com"
# (url, kind, what it is). kind: route-list = a real OpenAPI document answers; no-key = 200 without a key;
# login = anything but 401/403.
CLOSED_URLS = (
	("https://brain.sanadeoi.mvpstorm.com/openapi.json", "route-list", "Sanad Brain route list"),
	("https://brain.sanadeoi.mvpstorm.com/admin/audit", "no-key", "Sanad Brain audit log without a key"),
	(
		"https://brain.sanadeoi.mvpstorm.com/admin/agents/activity",
		"no-key",
		"Sanad Brain agent activity without a key",
	),
	(
		"https://lipton-anwar-wa.sandbox.sanadeoi.mvpstorm.com/openapi.json",
		"route-list",
		"Anwar bridge route list",
	),
	(PREVIEW + "/", "login", "Sanad Preview home without its login"),
	(PREVIEW + "/research/", "login", "Sanad Preview research without its login"),
	(PREVIEW + "/plans/", "login", "Sanad Preview plans without its login"),
)
HOST_RULE = re.compile(r"Host\(`([^`]+)`\)")
FIX = {
	"Open port": "bind it to 127.0.0.1 in compose, or put the service behind Traefik",
	"route-list": "FastAPI(openapi_url=None)",
	"no-key": "require the API key on this route",
	"login": "restore the login (Traefik basicauth middleware)",
}


def open_ports(ip, ports=SERVICE_PORTS, connect=socket.create_connection):
	"""Ports on ip that accept a TCP connection from here."""

	def try_port(port):
		try:
			connect((ip, port), timeout=2).close()
			return port
		except OSError:
			return None

	with concurrent.futures.ThreadPoolExecutor(16) as pool:
		return sorted(p for p in pool.map(try_port, ports) if p)


def vantage_command(ip, ports=SERVICE_PORTS):
	"""Shell command for the vantage server: print each port of ip that accepts a connection. Built from constants."""
	checks = " ".join(f"(timeout 2 bash -c '</dev/tcp/{ip}/{p}' 2>/dev/null && echo {p}) &" for p in ports)
	return f"{checks} wait"


def fetch(url, timeout=6):
	"""(status, first 4 KB of the body). Never raises; a network failure is status 0."""
	try:
		req = urllib.request.Request(url, headers={"User-Agent": "watch-tower-exposure"})
		with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as resp:
			return resp.status, resp.read(4096)
	except urllib.error.HTTPError as e:
		return e.code, b""
	except Exception:
		return 0, b""


def is_open(kind, status, body):
	if kind == "route-list":
		return status == 200 and b'"openapi"' in body
	if kind == "no-key":
		return status == 200
	return status not in (0, 401, 403)  # login; 0 = unreachable, which the site-reachability check covers


def collect(probe=open_ports, probe_press_ctrl=None, get=fetch, extra_hosts=()):
	"""Findings as (kind, where, what) tuples, sorted."""
	findings = []
	for name, ip in SERVERS.items():
		ports = probe_press_ctrl(ip) if name == "press-ctrl" and probe_press_ctrl else probe(ip)
		findings += [
			("Open port", f"{name} {ip}:{p}", "reachable from the internet")
			for p in ports
			if (name, p) not in ALLOWED_PORTS
		]
	urls = list(CLOSED_URLS) + [
		(f"https://{h}/openapi.json", "route-list", f"{h} route list") for h in sorted(set(extra_hosts))
	]
	with concurrent.futures.ThreadPoolExecutor(12) as pool:
		results = list(pool.map(lambda u: (u, get(u[0])), urls))
	findings += [
		(kind, url, what) for (url, kind, what), (status, body) in results if is_open(kind, status, body)
	]
	return sorted(set(findings))


def traefik_hosts(labels_text):
	"""Host names from Traefik router rules in `docker inspect` label output."""
	return sorted({h for h in HOST_RULE.findall(labels_text) if "*" not in h and "{" not in h})


def check_public_exposure(doc_dict, rule):
	"""Watch Tower Python Method. Global, so memoized: the engine calls it once per candidate document."""
	from .scheduler_alerts import _memoized

	return _memoized("public_exposure", _eval_public_exposure)


def _eval_public_exposure():
	from ..email_branding import send_alert_email, wrap_email
	from ._helpers import TABLE, esc, should_send_alert, ssh_cmd, ts_now

	def press_ctrl_from_vantage(ip):
		ok, out, _ = ssh_cmd(PRESS_CTRL_VANTAGE, vantage_command(ip), timeout=30)
		return sorted(int(x) for x in out.split() if x.isdigit()) if ok else []

	_, labels, _ = ssh_cmd(
		SERVERS["press-ctrl"],
		"docker ps -q | xargs -r docker inspect --format '{{range $k, $v := .Config.Labels}}{{$v}} {{end}}'",
		timeout=30,
	)
	findings = collect(probe_press_ctrl=press_ctrl_from_vantage, extra_hosts=traefik_hosts(labels))
	if not findings:
		return False
	if not should_send_alert("public_exposure", "|".join(f"{k} {w}" for k, w, _ in findings)):
		return True
	ts = ts_now()
	rows = "".join(
		f"<tr><td>{esc(k)}</td><td>{esc(w)}</td><td>{esc(what)}</td><td>{esc(FIX[k])}</td></tr>"
		for k, w, what in findings
	)
	body = (
		f'<table {TABLE}><tr style="background:#f8fafc"><th>Kind</th><th>Where</th><th>What</th><th>Fix</th></tr>'
		f'{rows}</table><p style="margin-top:12px">Checked from outside: press-ctrl probes the other servers, '
		f"accubuild-stg probes press-ctrl.</p>"
	)
	send_alert_email(
		recipients=["eng.elgogary@gmail.com"],
		subject=f"Exposure: {len(findings)} open to the internet - {ts}",
		message=wrap_email("Exposure watch", body, f"Press Infrastructure &bull; {ts}"),
	)
	return True
