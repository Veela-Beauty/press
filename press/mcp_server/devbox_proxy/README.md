# Dev-box stdio MCP proxy

Bridges a standard MCP stdio client (Claude Code `type: stdio`) to the Press
single-call RPC `press.mcp_server.server.handle`. Canonical source for the
proxy that runs on the Hetzner dev box at ~/data/press-mcp-proxy/.

tools/list is served from press_tools_catalog.json (regenerate when tools
change: dump TOOLS name->{description,inputSchema}). tools/call forwards to
handle(). Token via PRESS_MCP_TOKEN env (Press MCP Token, get_password value).
