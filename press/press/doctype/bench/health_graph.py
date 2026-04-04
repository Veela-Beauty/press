"""
Code graph extraction — builds module/class/function dependency graphs.
Two strategies:
  1. codegraph index (high quality, needs npm package)
  2. AST fallback (Python-only, no dependencies)

Called from bench_code_health.py (the @whitelist stub).
"""
import json
import re

from .bench_code_health import _exec, _safe


def extract_codegraph(bench, app):
    """Run codegraph init + index inside Docker, extract graph from SQLite DB."""
    app = _safe(app)

    # Check if codegraph is available
    r = _exec(bench, "which codegraph 2>/dev/null || echo MISSING")
    if "MISSING" in r.get("output", ""):
        # Try installing
        r = _exec(bench, "npm install -g @anthropic-ai/codegraph 2>/dev/null && echo OK || echo FAIL")
        if "FAIL" in r.get("output", ""):
            raise Exception("codegraph not available and could not install")

    # Init and index
    _exec(bench, f"cd apps/{app} && codegraph init . 2>/dev/null; codegraph index . 2>/dev/null")

    # Extract nodes from SQLite
    nodes_cmd = (
        f"sqlite3 apps/{app}/.codegraph/codegraph.db "
        "\"SELECT json_group_array(json_object("
        "'id', file || '/' || name, "
        "'label', name, "
        "'type', CASE WHEN kind='class' THEN 'class' WHEN kind='function' THEN 'function' ELSE 'function' END, "
        "'file', file, "
        "'line', line"
        ")) FROM symbols WHERE file NOT LIKE '%test%' AND file NOT LIKE '%__pycache__%' LIMIT 500\""
    )
    r = _exec(bench, nodes_cmd)
    raw_nodes = r.get("output", "[]").strip()

    # Extract edges
    edges_cmd = (
        f"sqlite3 apps/{app}/.codegraph/codegraph.db "
        "\"SELECT json_group_array(json_object("
        "'source', caller_file || '/' || caller_name, "
        "'target', callee_file || '/' || callee_name, "
        "'weight', 1, "
        "'layer', 'call'"
        ")) FROM edges WHERE caller_file NOT LIKE '%test%' LIMIT 1000\""
    )
    r = _exec(bench, edges_cmd)
    raw_edges = r.get("output", "[]").strip()

    try:
        nodes = json.loads(raw_nodes) if raw_nodes else []
        edges = json.loads(raw_edges) if raw_edges else []
    except json.JSONDecodeError:
        raise Exception("Failed to parse codegraph SQLite output")

    # Build module grouping from file paths
    modules = {}
    for node in nodes:
        parts = node.get("file", "").split("/")
        mod = parts[0] if parts else "root"
        if mod not in modules:
            modules[mod] = {"name": mod, "files": set(), "classes": 0, "functions": 0}
        modules[mod]["files"].add(node.get("file", ""))
        if node["type"] == "class":
            modules[mod]["classes"] += 1
        else:
            modules[mod]["functions"] += 1
        node["module"] = mod

    # Add module-level nodes
    module_nodes = []
    for mod_name, mod in modules.items():
        module_nodes.append({
            "id": mod_name, "label": mod_name, "type": "module",
            "files": len(mod["files"]), "classes": mod["classes"], "functions": mod["functions"],
        })

    # Aggregate edges to module level
    module_edges = {}
    for edge in edges:
        s_mod = edge["source"].split("/")[0] if "/" in edge["source"] else "root"
        t_mod = edge["target"].split("/")[0] if "/" in edge["target"] else "root"
        if s_mod != t_mod:
            key = f"{s_mod}->{t_mod}"
            if key not in module_edges:
                module_edges[key] = {"source": s_mod, "target": t_mod, "weight": 0, "layer": "import"}
            module_edges[key]["weight"] += 1

    return {
        "nodes": module_nodes + nodes,
        "edges": list(module_edges.values()) + edges,
    }


def extract_ast_graph(bench, app):
    """Fallback: extract graph using Python AST analysis (no codegraph needed)."""
    app = _safe(app)

    # Get all Python files
    r = _exec(bench, f"find apps/{app} -name '*.py' -not -path '*__pycache__*' -not -path '*.git*' -not -path '*test*' | head -200")
    files = [f.strip() for f in r.get("output", "").strip().split("\n") if f.strip()]

    nodes = []
    edges = []
    modules = {}

    for filepath in files:
        # Get module from path
        rel = filepath.replace(f"apps/{app}/", "")
        parts = rel.split("/")
        mod = parts[0] if len(parts) > 1 else "root"

        if mod not in modules:
            modules[mod] = {"name": mod, "files": set(), "classes": 0, "functions": 0}
        modules[mod]["files"].add(rel)

        # Extract functions and classes via grep (fast, no AST parsing in Docker)
        r = _exec(bench, f"grep -n '^class \\|^def \\|^async def ' {filepath} 2>/dev/null | head -50")
        for line in r.get("output", "").strip().split("\n"):
            if not line.strip():
                continue
            m = re.match(r"(\d+):(class|def|async def)\s+(\w+)", line.strip())
            if m:
                lineno, kind, name = m.group(1), m.group(2), m.group(3)
                node_type = "class" if kind == "class" else "function"
                nodes.append({
                    "id": f"{mod}/{name}", "label": name, "type": node_type,
                    "module": mod, "file": rel, "line": int(lineno),
                })
                modules[mod]["classes" if node_type == "class" else "functions"] += 1

        # Extract imports for edges
        r = _exec(bench, f"grep -n '^from \\|^import ' {filepath} 2>/dev/null | head -30")
        for line in r.get("output", "").strip().split("\n"):
            if not line.strip():
                continue
            # Match: from .module import X or from app.module import X
            im = re.match(r"\d+:from\s+\.?(\w+)", line.strip())
            if im:
                target_mod = im.group(1)
                if target_mod != mod and target_mod in modules:
                    key = f"{mod}->{target_mod}"
                    edges.append({"source": mod, "target": target_mod, "weight": 1, "layer": "import"})

    # Deduplicate module-level edges
    seen = {}
    deduped_edges = []
    for e in edges:
        key = f"{e['source']}->{e['target']}"
        if key in seen:
            seen[key]["weight"] += 1
        else:
            seen[key] = dict(e)
            deduped_edges.append(seen[key])

    # Module nodes
    module_nodes = [
        {"id": mod_name, "label": mod_name, "type": "module",
         "files": len(mod["files"]), "classes": mod["classes"], "functions": mod["functions"]}
        for mod_name, mod in modules.items()
    ]

    return {
        "nodes": module_nodes + nodes,
        "edges": deduped_edges,
    }
