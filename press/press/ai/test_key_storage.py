"""Tests for AI provider key storage — encryption, resolution chain, validation.

Keys are encrypted with AES-256-GCM before storage. Resolution chain:
  Personal key -> Company shared key -> Error (no platform default).

Pure Python — no Frappe DB dependency.
"""

import unittest


class TestKeyEncryption(unittest.TestCase):
    """Test AES-256-GCM encryption/decryption of API keys."""

    def test_encrypt_decrypt_roundtrip(self):
        from press.press.ai.key_storage import encrypt_key, decrypt_key

        master = "a" * 32  # 256-bit master key
        plaintext = "sk-ant-api03-abc123xyz"
        encrypted = encrypt_key(plaintext, master)
        decrypted = decrypt_key(encrypted, master)
        self.assertEqual(decrypted, plaintext)

    def test_encrypted_is_not_plaintext(self):
        from press.press.ai.key_storage import encrypt_key

        master = "b" * 32
        plaintext = "sk-ant-api03-abc123xyz"
        encrypted = encrypt_key(plaintext, master)
        self.assertNotEqual(encrypted, plaintext)
        self.assertNotIn("sk-ant", encrypted)

    def test_different_encryptions_produce_different_ciphertext(self):
        """Nonce should be random — same key encrypted twice should differ."""
        from press.press.ai.key_storage import encrypt_key

        master = "c" * 32
        plaintext = "sk-test-key"
        enc1 = encrypt_key(plaintext, master)
        enc2 = encrypt_key(plaintext, master)
        self.assertNotEqual(enc1, enc2)

    def test_wrong_master_key_fails(self):
        from press.press.ai.key_storage import encrypt_key, decrypt_key

        master1 = "d" * 32
        master2 = "e" * 32
        encrypted = encrypt_key("sk-secret", master1)
        with self.assertRaises(Exception):
            decrypt_key(encrypted, master2)

    def test_empty_key_raises(self):
        from press.press.ai.key_storage import encrypt_key

        master = "f" * 32
        with self.assertRaises(ValueError):
            encrypt_key("", master)

    def test_short_master_key_raises(self):
        from press.press.ai.key_storage import encrypt_key

        with self.assertRaises(ValueError):
            encrypt_key("sk-test", "short")


class TestProviderResolution(unittest.TestCase):
    """Test the key resolution chain: Personal -> Company -> Error."""

    def test_personal_key_takes_priority(self):
        from press.press.ai.key_storage import resolve_provider_key

        result = resolve_provider_key(
            personal_key="sk-personal",
            company_key="sk-company",
            provider="anthropic",
        )
        self.assertEqual(result.key, "sk-personal")
        self.assertEqual(result.source, "personal")

    def test_company_key_fallback(self):
        from press.press.ai.key_storage import resolve_provider_key

        result = resolve_provider_key(
            personal_key=None,
            company_key="sk-company",
            provider="anthropic",
        )
        self.assertEqual(result.key, "sk-company")
        self.assertEqual(result.source, "company")

    def test_no_key_returns_error(self):
        from press.press.ai.key_storage import resolve_provider_key

        result = resolve_provider_key(
            personal_key=None,
            company_key=None,
            provider="anthropic",
        )
        self.assertIsNone(result.key)
        self.assertEqual(result.source, "none")
        self.assertIn("configure", result.error.lower())

    def test_empty_string_key_treated_as_none(self):
        from press.press.ai.key_storage import resolve_provider_key

        result = resolve_provider_key(
            personal_key="",
            company_key="",
            provider="anthropic",
        )
        self.assertIsNone(result.key)
        self.assertEqual(result.source, "none")

    def test_result_includes_provider(self):
        from press.press.ai.key_storage import resolve_provider_key

        result = resolve_provider_key(
            personal_key="sk-test",
            company_key=None,
            provider="z_ai",
        )
        self.assertEqual(result.provider, "z_ai")


class TestKeyValidation(unittest.TestCase):
    """Test basic key format validation."""

    def test_anthropic_key_format(self):
        from press.press.ai.key_storage import validate_key_format

        self.assertTrue(validate_key_format("sk-ant-api03-abc123", "anthropic"))
        self.assertFalse(validate_key_format("not-a-key", "anthropic"))

    def test_openai_key_format(self):
        from press.press.ai.key_storage import validate_key_format

        self.assertTrue(validate_key_format("sk-proj-abc123def456", "openai"))
        self.assertTrue(validate_key_format("sk-abc123def456", "openai"))
        self.assertFalse(validate_key_format("not-a-key", "openai"))

    def test_custom_provider_accepts_any(self):
        from press.press.ai.key_storage import validate_key_format

        self.assertTrue(validate_key_format("any-key-format", "custom"))

    def test_empty_key_always_invalid(self):
        from press.press.ai.key_storage import validate_key_format

        self.assertFalse(validate_key_format("", "anthropic"))
        self.assertFalse(validate_key_format("", "openai"))


class TestProviderConfig(unittest.TestCase):
    """Test provider endpoint configuration."""

    def test_anthropic_config(self):
        from press.press.ai.key_storage import get_provider_config

        cfg = get_provider_config("anthropic")
        self.assertIn("api.anthropic.com", cfg.base_url)
        self.assertEqual(cfg.default_model, "claude-sonnet-4-20250514")

    def test_openai_config(self):
        from press.press.ai.key_storage import get_provider_config

        cfg = get_provider_config("openai")
        self.assertIn("api.openai.com", cfg.base_url)

    def test_z_ai_config(self):
        from press.press.ai.key_storage import get_provider_config

        cfg = get_provider_config("z_ai")
        self.assertIn("z.ai", cfg.base_url)

    def test_custom_provider_with_base_url(self):
        from press.press.ai.key_storage import get_provider_config

        cfg = get_provider_config("custom", base_url="http://localhost:11434/v1")
        self.assertEqual(cfg.base_url, "http://localhost:11434/v1")

    def test_unknown_provider_raises(self):
        from press.press.ai.key_storage import get_provider_config

        with self.assertRaises(ValueError):
            get_provider_config("nonexistent")


if __name__ == "__main__":
    unittest.main()
