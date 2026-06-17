"""
Guard tests for the verification harness scripts.

Verifies two safety properties:
1. The seed/reset/snapshot scripts refuse to run against a non-verification
   database name (exit code 4).
2. The repo default keeps DEV_AUTH_BYPASS off, so the bypass is never on by
   default.
"""

import pytest

from app.config import Settings, get_settings
from app.scripts import _verify_guard


class TestVerificationDbGuard:
    def test_is_verification_db_true_for_configured_db(self):
        settings = get_settings()
        assert _verify_guard.is_verification_db(settings.verification_database_url)

    def test_is_verification_db_false_for_dev_db(self):
        settings = get_settings()
        assert not _verify_guard.is_verification_db(settings.database_url)

    def test_assert_refuses_non_verification_db(self):
        settings = get_settings()
        with pytest.raises(SystemExit) as exc:
            _verify_guard.assert_verification_db(settings.database_url)
        assert exc.value.code == _verify_guard.EXIT_REFUSED_NOT_VERIFICATION_DB

    def test_assert_allows_verification_db(self):
        settings = get_settings()
        # Should not raise / exit.
        _verify_guard.assert_verification_db(settings.verification_database_url)

    def test_resolve_falls_back_to_configured_url(self):
        settings = get_settings()
        assert _verify_guard.resolve_verification_url(None) == settings.verification_database_url

    def test_resolve_uses_explicit_url(self):
        explicit = "postgresql://u:p@host:5432/pacman_verify"
        assert _verify_guard.resolve_verification_url(explicit) == explicit


class TestBypassDefaultOff:
    def test_dev_auth_bypass_defaults_off(self, monkeypatch):
        """Default settings (no env override) must keep the bypass disabled."""
        # Ignore any ambient env var so we assert the code default, not the shell.
        monkeypatch.delenv("DEV_AUTH_BYPASS", raising=False)
        # Construct settings ignoring any .env so we assert the code default.
        defaults = Settings(_env_file=None)
        assert defaults.dev_auth_bypass is False

    def test_env_example_documents_bypass_off(self):
        """The committed .env.example must not enable the bypass."""
        from pathlib import Path

        env_example = Path(__file__).resolve().parents[2] / ".env.example"
        if env_example.exists():
            text = env_example.read_text(encoding="utf-8")
            for line in text.splitlines():
                stripped = line.strip()
                if stripped.upper().startswith("DEV_AUTH_BYPASS"):
                    assert stripped.split("=", 1)[1].strip() in {"0", "false", "False", ""}
