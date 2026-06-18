#!/usr/bin/env python3
"""Stdio MCP proxy for the Press MCP.

The Press MCP exposes a single Frappe RPC (`press.mcp_server.server.handle`),
NOT the MCP wire protocol, so a standard MCP client (Claude Code `type: stdio`)
can't talk to it directly. This proxy bridges the two:

  - `tools/list`  is served from a static snapshot (press_tools_catalog.json,
    sibling file) so clients get every tool name + real JSON-Schema inputSchema.
  - `tools/call`  forwards to `handle(tool, args, token)` over HTTP and maps the
    `{message:{ok,data}}` reply into the MCP content shape.

Reaches the control plane via fixed IP + Host header because the control-plane
site name (demo.mvpstorm.com) has no public cert that matches; TLS verify is off
by default for that internal, fixed-IP call (the token in the body is the auth).

Env:
  PRESS_MCP_TOKEN     Press MCP token (required)
  PRESS_MCP_URL       handle() URL  (default: https://89.167.116.92/api/method/press.mcp_server.server.handle)
  PRESS_MCP_HOST      Host header    (default: demo.mvpstorm.com)
  PRESS_MCP_INSECURE  '1' skip TLS verify (default '1')

Regenerate the catalog when tools change:
  bench --site demo.mvpstorm.com execute press.mcp_server... (dump TOOLS) > press_tools_catalog.json
"""
import json
import os
import ssl
import sys
import urllib.parse
import urllib.request

URL = os.environ.get(
    "PRESS_MCP_URL",
    "https://89.167.116.92/api/method/press.mcp_server.server.handle",
)
HOST = os.environ.get("PRESS_MCP_HOST", "demo.mvpstorm.com")
TOKEN = os.environ.get("PRESS_MCP_TOKEN", "")
INSECURE = os.environ.get("PRESS_MCP_INSECURE", "1") == "1"
PROTOCOL = "2024-11-05"
HERE = os.path.dirname(os.path.abspath(__file__))


def _catalog():
    try:
        with open(os.path.join(HERE, "press_tools_catalog.json")) as fh:
            return json.load(fh)
    except Exception:
        return {}


def _ssl_ctx():
    if not INSECURE:
        return None
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _call_press(tool, args):
    data = urllib.parse.urlencode(
        {"tool": tool, "token": TOKEN, "args": json.dumps(args or {})}
    ).encode()
    req = urllib.request.Request(URL, data=data, method="POST")
    req.add_header("Host", HOST)
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req, timeout=120, context=_ssl_ctx()) as resp:
        body = resp.read().decode()
    obj = json.loads(body)
    return obj.get("message", obj)


def _send(msg):
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def _result(rid, result):
    _send({"jsonrpc": "2.0", "id": rid, "result": result})


def _error(rid, code, message):
    _send({"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}})


def _tools_list():
    cat = _catalog()
    return [
        {
            "name": name,
            "description": meta.get("description", ""),
            "inputSchema": meta.get("inputSchema") or {"type": "object", "properties": {}},
        }
        for name, meta in cat.items()
    ]


def handle_msg(msg):
    method = msg.get("method")
    rid = msg.get("id")
    if method == "initialize":
        _result(rid, {
            "protocolVersion": PROTOCOL,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "press-mcp", "version": "1.0.0"},
        })
        return
    if method in ("notifications/initialized", "notifications/cancelled"):
        return  # notifications carry no id and take no response
    if method == "ping":
        _result(rid, {})
        return
    if method == "tools/list":
        _result(rid, {"tools": _tools_list()})
        return
    if method == "tools/call":
        params = msg.get("params") or {}
        name = params.get("name")
        args = params.get("arguments") or {}
        try:
            res = _call_press(name, args)
        except Exception as exc:
            _error(rid, -32000, f"press call failed: {exc}")
            return
        ok = res.get("ok", True) if isinstance(res, dict) else True
        payload = res.get("data") if isinstance(res, dict) and "data" in res else res
        text = payload if isinstance(payload, str) else json.dumps(payload, indent=2, default=str)
        if not ok:
            text = json.dumps(res, indent=2, default=str)
        _result(rid, {"content": [{"type": "text", "text": text}], "isError": not ok})
        return
    if rid is not None:
        _error(rid, -32601, f"method not found: {method}")


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            continue
        try:
            handle_msg(msg)
        except Exception as exc:
            try:
                _error(msg.get("id"), -32603, f"internal: {exc}")
            except Exception:
                pass


if __name__ == "__main__":
    main()
