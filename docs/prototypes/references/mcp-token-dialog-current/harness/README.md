Renders the deployed IssueTokenDialog.vue offline (real frappe-ui 0.1.238, faked `call`).

1. npm install
2. mkdir -p src/mcp && cp ../../../../../dashboard/src/components/mcp/{IssueTokenDialog.vue,MultiSelectChips.vue,HandoverPanel.vue,_tool_catalog.js} src/mcp/
3. npx vite build && npx vite preview --port 5199
4. python3 shoot.py http://localhost:5199/ <out-dir>
5. python3 shoot_proto.py ../../mcp_token_confidential_pin_prototype.html <out-dir>   (prototype states + layout probe)
