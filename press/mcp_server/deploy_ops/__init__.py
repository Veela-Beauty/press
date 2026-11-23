"""The deploy-flow MCP tools, split out of press/mcp_server/deploy_flow.py by concern (0.7.54).

deploy_flow.py re-exports every name, so the tool catalog's method paths (press.mcp_server.deploy_flow.<tool>) and
`from press.mcp_server.deploy_flow import ...` keep working. Patch a function where it now lives
(press.mcp_server.deploy_ops.<module>.<name>), since that is where its callers look it up.
"""
