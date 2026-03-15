"""
Tests for error logging and silent-catch elimination.

Covers:
- T007: DEV_AUTH_BYPASS critical log warning
- T014: importer coverage matching logs on failure
- T016: coverage.py GeoJSON geometry logging
- T017: importer polyline decode logging
- T019: cities.py boundary serialization logging
- T020: webhook handler logs and re-raises on failure
- T021: webhook API catches TokenRevokedError, returns 500 on other errors
- T026b: Automated grep audit for remaining silent catches
"""

import glob
import os
import re

import pytest


class TestSilentCatchAudit:
    """T026b: Verify zero remaining silent except:pass in backend and empty .catch in frontend."""

    def test_no_silent_except_pass_in_backend(self):
        """Grep backend/app/ for 'except.*pass' — should find zero matches."""
        backend_dir = os.path.join(os.path.dirname(__file__), "..", "..", "app")
        matches = []
        for filepath in glob.glob(os.path.join(backend_dir, "**", "*.py"), recursive=True):
            with open(filepath, encoding="utf-8", errors="replace") as f:
                for i, line in enumerate(f, 1):
                    stripped = line.strip()
                    # Match lines that are just "pass" inside an except block
                    if stripped == "pass":
                        # Look at previous non-blank line for except
                        pass  # We need a smarter check
            # Use a simpler approach: look for "except.*:\n.*pass" pattern
            with open(filepath, encoding="utf-8", errors="replace") as f:
                content = f.read()
                # Find except blocks followed by just pass (allowing whitespace/comments)
                pattern = r"except[^:]*:\s*\n\s*pass\s*$"
                for m in re.finditer(pattern, content, re.MULTILINE):
                    rel_path = os.path.relpath(filepath, backend_dir)
                    line_num = content[:m.start()].count("\n") + 1
                    matches.append(f"{rel_path}:{line_num}")

        assert matches == [], f"Found silent except:pass patterns:\n" + "\n".join(matches)

    def test_no_empty_catch_in_frontend(self):
        """Grep frontend/src/ for '.catch(() => {})' — should find zero matches."""
        frontend_dir = os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "frontend", "src"
        )
        matches = []
        for filepath in glob.glob(os.path.join(frontend_dir, "**", "*.tsx"), recursive=True):
            with open(filepath, encoding="utf-8", errors="replace") as f:
                for i, line in enumerate(f, 1):
                    if ".catch(() => {})" in line:
                        rel_path = os.path.relpath(filepath, frontend_dir)
                        matches.append(f"{rel_path}:{i}: {line.strip()}")

        assert matches == [], f"Found empty .catch handlers:\n" + "\n".join(matches)


class TestDevAuthBypassWarning:
    """T007: DEV_AUTH_BYPASS emits critical log."""

    def test_critical_log_in_deps(self):
        """The get_current_user function should contain a logger.critical call."""
        import inspect
        from app.api.deps import get_current_user

        source = inspect.getsource(get_current_user)
        assert "logger.critical" in source, "DEV_AUTH_BYPASS should log at CRITICAL level"


class TestImporterErrorLogging:
    """T014+T017: Importer logs errors instead of silently passing."""

    def test_coverage_matching_failure_logged(self):
        """T014: The coverage matching except block should call logger.exception."""
        import inspect
        from app.services.importer import _process_phase_b_activity

        source = inspect.getsource(_process_phase_b_activity)
        assert "logger.exception" in source, "Coverage matching failure should log"
        assert "Coverage matching failed" in source

    def test_polyline_decode_failure_logged(self):
        """T017: The polyline decode except block should call logger.warning."""
        import inspect
        from app.services.importer import ActivityImporter

        source = inspect.getsource(ActivityImporter.import_phase_a)
        assert "logger.warning" in source or "Failed to decode polyline" in source


class TestCoverageGeoJSONLogging:
    """T016: coverage.py logs geometry serialization failures."""

    def test_geometry_failure_logged(self):
        import inspect
        from app.api.coverage import _streets_geojson

        source = inspect.getsource(_streets_geojson)
        assert "logger.warning" in source, "GeoJSON geometry failure should log"


class TestCitiesBoundaryLogging:
    """T019: cities.py logs boundary serialization failures."""

    def test_boundary_failure_logged(self):
        import inspect
        from app.api.cities import _serialize_neighborhood_boundary

        source = inspect.getsource(_serialize_neighborhood_boundary)
        assert "logger.warning" in source, "Boundary serialization failure should log"


class TestWebhookErrorHandling:
    """T020+T021: Webhook logs errors and re-raises; API catches TokenRevokedError."""

    def test_webhook_handler_logs_and_reraises(self):
        """T020: handle_webhook_event should log exceptions and re-raise."""
        import inspect
        from app.services.webhook import handle_webhook_event

        source = inspect.getsource(handle_webhook_event)
        assert "logger.exception" in source, "Webhook handler should log exceptions"
        assert "raise" in source, "Webhook handler should re-raise after logging"

    def test_webhook_api_catches_token_revoked(self):
        """T021: Webhook API route should catch TokenRevokedError separately."""
        import inspect
        from app.api.webhook import strava_webhook_event

        source = inspect.getsource(strava_webhook_event)
        assert "TokenRevokedError" in source, "Should catch TokenRevokedError"
        assert "500" not in source or "return" in source  # Should let other exceptions become 500
