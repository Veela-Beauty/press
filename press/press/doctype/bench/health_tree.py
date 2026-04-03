"""
Tree builders for circle-packing visualization.
Called from bench_code_health.py (the @whitelist stub).
"""

from .bench_code_health import CODE_EXTS, HARD_LIMIT, SOFT_LIMIT


def build_tree(file_data, root_name):
    """Build nested tree from flat {filepath: lines} dict."""
    root = {"name": root_name, "children": []}
    for filepath, lines in sorted(file_data.items()):
        parts = filepath.split("/")
        if parts[0] == "apps":
            parts = parts[1:]
        node = root
        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                ext = "." + part.rsplit(".", 1)[-1] if "." in part else ""
                health = "non-code"
                if ext in CODE_EXTS:
                    health = "violation" if lines > HARD_LIMIT else "warning" if lines > SOFT_LIMIT else "clean"
                node["children"].append({"name": part, "ext": ext, "lines": lines, "health": health})
            else:
                existing = next((c for c in node.get("children", []) if c.get("name") == part and "children" in c), None)
                if not existing:
                    existing = {"name": part, "children": []}
                    node.setdefault("children", []).append(existing)
                node = existing
    return root


def compute_stats(tree):
    """Recursively compute health stats and health_pct per tree node."""
    if "children" not in tree:
        is_code = tree.get("ext", "") in CODE_EXTS
        return {"total_files": 1 if is_code else 0, "total_lines": tree.get("lines", 0),
                "clean": 1 if tree.get("health") == "clean" else 0,
                "warning": 1 if tree.get("health") == "warning" else 0,
                "violation": 1 if tree.get("health") == "violation" else 0}
    stats = {"total_files": 0, "total_lines": 0, "clean": 0, "warning": 0, "violation": 0}
    for child in tree["children"]:
        cs = compute_stats(child)
        for k in stats:
            stats[k] += cs[k]
    tree["stats"] = stats
    if stats["total_files"] > 0:
        tree["health_pct"] = round(stats["clean"] / stats["total_files"] * 100)
    return stats
