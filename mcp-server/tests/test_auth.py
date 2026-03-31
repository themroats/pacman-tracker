"""Tests for credential caching in auth.py."""

from __future__ import annotations

import json

import pytest

from pacman_mcp.auth import _load_cached_credentials, _save_credentials


class TestCredentialCaching:
    def test_save_and_load(self, tmp_path, monkeypatch):
        cred_file = tmp_path / "credentials.json"
        monkeypatch.setattr("pacman_mcp.auth.CREDENTIAL_FILE", cred_file)
        monkeypatch.setattr("pacman_mcp.auth.CREDENTIAL_DIR", tmp_path)

        data = {
            "access_token": "tok_abc123",
            "strava_athlete_id": 12345,
            "user_id": 1,
            "display_name": "Test User",
        }
        _save_credentials(data)

        assert cred_file.exists()
        loaded = _load_cached_credentials()
        assert loaded is not None
        assert loaded["access_token"] == "tok_abc123"
        assert loaded["strava_athlete_id"] == 12345

    def test_load_missing_file(self, tmp_path, monkeypatch):
        cred_file = tmp_path / "nonexistent.json"
        monkeypatch.setattr("pacman_mcp.auth.CREDENTIAL_FILE", cred_file)

        assert _load_cached_credentials() is None

    def test_load_invalid_json(self, tmp_path, monkeypatch):
        cred_file = tmp_path / "credentials.json"
        cred_file.write_text("not json{{{")
        monkeypatch.setattr("pacman_mcp.auth.CREDENTIAL_FILE", cred_file)

        assert _load_cached_credentials() is None

    def test_load_missing_fields(self, tmp_path, monkeypatch):
        cred_file = tmp_path / "credentials.json"
        cred_file.write_text(json.dumps({"access_token": "tok", "some_other": "field"}))
        monkeypatch.setattr("pacman_mcp.auth.CREDENTIAL_FILE", cred_file)

        # Missing strava_athlete_id → should return None
        assert _load_cached_credentials() is None

    def test_load_empty_token(self, tmp_path, monkeypatch):
        cred_file = tmp_path / "credentials.json"
        cred_file.write_text(json.dumps({"access_token": "", "strava_athlete_id": 123}))
        monkeypatch.setattr("pacman_mcp.auth.CREDENTIAL_FILE", cred_file)

        assert _load_cached_credentials() is None

    def test_save_creates_directory(self, tmp_path, monkeypatch):
        nested = tmp_path / "sub" / "dir"
        cred_file = nested / "credentials.json"
        monkeypatch.setattr("pacman_mcp.auth.CREDENTIAL_FILE", cred_file)
        monkeypatch.setattr("pacman_mcp.auth.CREDENTIAL_DIR", nested)

        _save_credentials({"access_token": "tok", "strava_athlete_id": 1})
        assert cred_file.exists()
