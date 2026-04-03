"""
External code analysis service integration.
Sends git URL + commit to analysis microservice, returns dual format:
  - HTML: human-readable rendered graphs
  - JSON: structured data for AI agents

Auth: Bearer token from Press Settings → analysis service validates.
Cache: Redis, keyed by (git_url, commit_hash), 24h TTL.
"""

import json
import frappe
import requests

CACHE_TTL = 3600 * 24  # 24 hours


def _get_analysis_config():
    """Read analysis service config from site_config.json."""
    return {
        "url": frappe.conf.get("code_analysis_service_url", ""),
        "token": frappe.conf.get("code_analysis_service_token", ""),
    }


def _cache_key(git_url, commit):
    return f"code_analysis:{git_url}:{commit}"


def _call_analysis_service(git_url, commit_hash, config):
    """POST to external analysis service. Returns dict with html + json + meta."""
    resp = requests.post(
        f"{config['url'].rstrip('/')}/api/analyze",
        json={"git_url": git_url, "commit_hash": commit_hash},
        headers={"Authorization": f"Bearer {config['token']}"},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()


@frappe.whitelist()
def analyze_app_code(git_url, commit_hash, output_format="both"):
    """Analyze a codebase via external service. Returns HTML + JSON.

    Args:
        git_url: GitHub/git URL of the repository
        commit_hash: Git commit hash to analyze
        output_format: "html", "json", or "both" (default)

    Returns:
        dict with html, json, meta keys (filtered by output_format)
    """
    frappe.only_for("System Manager")

    # Validate inputs
    if not git_url or not git_url.strip():
        return {"error": "git_url is required"}
    if not commit_hash or not commit_hash.strip():
        return {"error": "commit_hash is required"}

    git_url = git_url.strip()
    commit_hash = commit_hash.strip()

    # Check config
    config = _get_analysis_config()
    if not config.get("url"):
        return {"error": "Analysis service URL not configured. Set code_analysis_service_url in site_config.json"}
    if not config.get("token"):
        return {"error": "Analysis service auth token not configured. Set code_analysis_service_token in site_config.json"}

    # Check cache
    cached = frappe.cache.get_value(_cache_key(git_url, commit_hash))
    if cached:
        try:
            data = json.loads(cached)
            return _filter_format(data, output_format)
        except (json.JSONDecodeError, TypeError):
            pass

    # Call external service
    try:
        data = _call_analysis_service(git_url, commit_hash, config)
    except Exception as e:
        return {"error": str(e)}

    # Cache successful result
    frappe.cache.set_value(
        _cache_key(git_url, commit_hash),
        json.dumps(data),
        expires_in_sec=CACHE_TTL,
    )

    return _filter_format(data, output_format)


def _filter_format(data, output_format):
    """Filter response to requested format."""
    result = {"meta": data.get("meta", {})}
    if output_format in ("html", "both"):
        result["html"] = data.get("html", "")
    if output_format in ("json", "both"):
        result["json"] = data.get("json", {})
    return result
