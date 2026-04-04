"""AI provider key storage — encryption, resolution chain, validation.

Keys are encrypted with AES-256-GCM before storage in Press DB.
Resolution chain: Personal -> Company shared -> Error (no platform default).

Pure Python core — Frappe DB operations are separate.
"""

import base64
import hashlib
import os
import re
from dataclasses import dataclass


# --- Encryption (AES-256-GCM) ---

def _derive_aes_key(master: str) -> bytes:
    """Derive a 256-bit AES key from the master key string."""
    if len(master) < 16:
        raise ValueError("Master key must be at least 16 characters")
    return hashlib.sha256(master.encode()).digest()


def encrypt_key(plaintext: str, master_key: str) -> str:
    """Encrypt an API key with AES-256-GCM. Returns base64-encoded nonce+ciphertext+tag."""
    if not plaintext:
        raise ValueError("Cannot encrypt empty key")
    if len(master_key) < 16:
        raise ValueError("Master key must be at least 16 characters")

    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    key = _derive_aes_key(master_key)
    nonce = os.urandom(12)  # 96-bit nonce for GCM
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
    # Pack: nonce (12) + ciphertext+tag
    return base64.b64encode(nonce + ciphertext).decode()


def decrypt_key(encrypted: str, master_key: str) -> str:
    """Decrypt an AES-256-GCM encrypted API key."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    key = _derive_aes_key(master_key)
    raw = base64.b64decode(encrypted)
    nonce = raw[:12]
    ciphertext = raw[12:]
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext.decode()


# --- Provider Resolution Chain ---

@dataclass
class ResolvedKey:
    key: str | None
    source: str  # "personal", "company", "none"
    provider: str
    error: str = ""


def resolve_provider_key(
    personal_key: str | None,
    company_key: str | None,
    provider: str,
) -> ResolvedKey:
    """Resolve which API key to use. Personal -> Company -> Error."""
    if personal_key and personal_key.strip():
        return ResolvedKey(key=personal_key.strip(), source="personal", provider=provider)

    if company_key and company_key.strip():
        return ResolvedKey(key=company_key.strip(), source="company", provider=provider)

    return ResolvedKey(
        key=None,
        source="none",
        provider=provider,
        error=f"No API key configured for {provider}. Please configure a personal or company key in Settings.",
    )


# --- Key Format Validation ---

KEY_PATTERNS = {
    "anthropic": re.compile(r"^sk-ant-"),
    "openai": re.compile(r"^sk-"),
    "z_ai": re.compile(r".{10,}"),  # Z.AI uses various formats, just check length
}


def validate_key_format(key: str, provider: str) -> bool:
    """Basic format validation for provider API keys."""
    if not key or not key.strip():
        return False

    pattern = KEY_PATTERNS.get(provider)
    if pattern is None:
        # Custom/unknown provider — accept any non-empty key
        return True

    return bool(pattern.match(key))


# --- Provider Configuration ---

@dataclass
class ProviderConfig:
    name: str
    base_url: str
    default_model: str
    api_format: str  # "anthropic" or "openai"


PROVIDERS = {
    "anthropic": ProviderConfig(
        name="Anthropic",
        base_url="https://api.anthropic.com/v1/messages",
        default_model="claude-sonnet-4-20250514",
        api_format="anthropic",
    ),
    "openai": ProviderConfig(
        name="OpenAI",
        base_url="https://api.openai.com/v1/chat/completions",
        default_model="gpt-4o",
        api_format="openai",
    ),
    "z_ai": ProviderConfig(
        name="Z.AI",
        base_url="https://api.z.ai/v1",
        default_model="glm-4-plus",
        api_format="openai",
    ),
}


def get_provider_config(provider: str, base_url: str = None) -> ProviderConfig:
    """Get configuration for a known provider, or build custom config."""
    if provider == "custom":
        if not base_url:
            raise ValueError("Custom provider requires base_url")
        return ProviderConfig(
            name="Custom",
            base_url=base_url,
            default_model="",
            api_format="openai",
        )

    config = PROVIDERS.get(provider)
    if config is None:
        raise ValueError(f"Unknown provider '{provider}'. Known: {', '.join(PROVIDERS.keys())}, custom")

    return config
