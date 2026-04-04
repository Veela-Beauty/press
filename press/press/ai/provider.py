"""AI provider — calls LLM APIs via OpenRouter or direct endpoints.

Supports OpenRouter (routes to 200+ models), Anthropic, OpenAI, Z.AI.
Uses the OpenAI-compatible chat/completions format for all providers.

Pure Python — uses urllib (no pip dependencies).
"""

import json
import urllib.request
import urllib.error

# Provider endpoint configuration
PROVIDER_ENDPOINTS = {
    "openrouter": "https://openrouter.ai/api/v1/chat/completions",
    "anthropic": "https://api.anthropic.com/v1/messages",
    "openai": "https://api.openai.com/v1/chat/completions",
    "z_ai": "https://api.z.ai/v1/chat/completions",
}

DEFAULT_MODELS = {
    "openrouter": "z-ai/glm-4.5-air",
    "anthropic": "claude-sonnet-4-20250514",
    "openai": "gpt-4o",
    "z_ai": "glm-4-plus",
}


def call_provider(
    prompt: str,
    api_key: str,
    provider: str = "openrouter",
    model: str = "",
    system_prompt: str = "",
    max_tokens: int = 4096,
    temperature: float = 0.3,
) -> dict:
    """Call an LLM provider and return the response.

    Args:
        prompt: User message text
        api_key: Provider API key
        provider: Provider name (openrouter, anthropic, openai, z_ai)
        model: Model ID (defaults per provider if empty)
        system_prompt: Optional system message
        max_tokens: Max response tokens
        temperature: Sampling temperature

    Returns: {"text": str, "input_tokens": int, "output_tokens": int, "model": str}
    Raises: Exception on API errors
    """
    if not model:
        model = DEFAULT_MODELS.get(provider, "")

    if provider == "anthropic":
        return _call_anthropic(prompt, api_key, model, system_prompt, max_tokens, temperature)

    # OpenAI-compatible format (OpenRouter, OpenAI, Z.AI, custom)
    return _call_openai_compatible(
        prompt, api_key, provider, model, system_prompt, max_tokens, temperature
    )


def _call_openai_compatible(
    prompt: str, api_key: str, provider: str, model: str,
    system_prompt: str, max_tokens: int, temperature: float,
) -> dict:
    """Call OpenAI-compatible API (OpenRouter, OpenAI, Z.AI)."""
    endpoint = PROVIDER_ENDPOINTS.get(provider)
    if not endpoint:
        raise ValueError(f"Unknown provider: {provider}")

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt or "Hello"})

    body = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    # OpenRouter-specific headers
    if provider == "openrouter":
        headers["HTTP-Referer"] = "https://autodeploypanel.mvpstorm.com"
        headers["X-Title"] = "Press AI Developer Assistant"

    req = urllib.request.Request(
        endpoint,
        data=json.dumps(body).encode(),
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else ""
        raise Exception(
            f"Provider API error ({e.code}): {error_body[:500]}"
        ) from e

    # Parse response
    choice = data.get("choices", [{}])[0]
    message = choice.get("message", {})
    usage = data.get("usage", {})

    return {
        "text": message.get("content", ""),
        "input_tokens": usage.get("prompt_tokens", 0),
        "output_tokens": usage.get("completion_tokens", 0),
        "model": data.get("model", model),
    }


def _call_anthropic(
    prompt: str, api_key: str, model: str,
    system_prompt: str, max_tokens: int, temperature: float,
) -> dict:
    """Call Anthropic Messages API (different format from OpenAI)."""
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt or "Hello"}],
    }
    if system_prompt:
        body["system"] = system_prompt

    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }

    req = urllib.request.Request(
        PROVIDER_ENDPOINTS["anthropic"],
        data=json.dumps(body).encode(),
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else ""
        raise Exception(
            f"Anthropic API error ({e.code}): {error_body[:500]}"
        ) from e

    # Parse Anthropic response format
    content_blocks = data.get("content", [])
    text = "".join(b.get("text", "") for b in content_blocks if b.get("type") == "text")
    usage = data.get("usage", {})

    return {
        "text": text,
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "model": data.get("model", model),
    }
