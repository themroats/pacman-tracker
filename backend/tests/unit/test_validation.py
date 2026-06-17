"""
Unit tests for input validation and database constraints.

Covers:
- FK pragma is ON
- T004b: SpatiaLite fail-fast
- distance_meters le=50000
- StartPoint coordinate validation
- BBox validation returns 400
- Path param gt=0 validation
"""

import pytest
from pydantic import ValidationError

from app.schemas.route import RouteSuggestRequest, StartPoint


class TestStartPointValidation:
    """Typed StartPoint model with coordinate range validation."""

    def test_valid_coordinates(self):
        sp = StartPoint(lng=-122.33, lat=47.60)
        assert sp.lng == -122.33
        assert sp.lat == 47.60

    def test_lng_too_high(self):
        with pytest.raises(ValidationError, match="less than or equal to 180"):
            StartPoint(lng=181, lat=0)

    def test_lng_too_low(self):
        with pytest.raises(ValidationError, match="greater than or equal to -180"):
            StartPoint(lng=-181, lat=0)

    def test_lat_too_high(self):
        with pytest.raises(ValidationError, match="less than or equal to 90"):
            StartPoint(lng=0, lat=91)

    def test_lat_too_low(self):
        with pytest.raises(ValidationError, match="greater than or equal to -90"):
            StartPoint(lng=0, lat=-91)

    def test_boundary_values_accepted(self):
        sp = StartPoint(lng=180, lat=90)
        assert sp.lng == 180
        sp = StartPoint(lng=-180, lat=-90)
        assert sp.lng == -180


class TestRouteSuggestRequestValidation:
    """Route request validation."""

    def test_valid_request(self):
        req = RouteSuggestRequest(
            start_point={"lng": -122.33, "lat": 47.60},
            distance_meters=5000,
            city_id=1,
        )
        assert req.distance_meters == 5000

    def test_distance_exceeds_50km(self):
        with pytest.raises(ValidationError, match="less than or equal to 50000"):
            RouteSuggestRequest(
                start_point={"lng": -122.33, "lat": 47.60},
                distance_meters=50001,
                city_id=1,
            )

    def test_distance_zero_rejected(self):
        with pytest.raises(ValidationError, match="greater than 0"):
            RouteSuggestRequest(
                start_point={"lng": -122.33, "lat": 47.60},
                distance_meters=0,
                city_id=1,
            )

    def test_negative_distance_rejected(self):
        with pytest.raises(ValidationError):
            RouteSuggestRequest(
                start_point={"lng": -122.33, "lat": 47.60},
                distance_meters=-100,
                city_id=1,
            )

    def test_invalid_coordinates_in_request(self):
        with pytest.raises(ValidationError):
            RouteSuggestRequest(
                start_point={"lng": 999, "lat": 47.60},
                distance_meters=5000,
                city_id=1,
            )

    def test_city_id_must_be_positive(self):
        with pytest.raises(ValidationError, match="greater than 0"):
            RouteSuggestRequest(
                start_point={"lng": -122.33, "lat": 47.60},
                distance_meters=5000,
                city_id=0,
            )

    def test_neighborhood_id_must_be_positive_when_provided(self):
        with pytest.raises(ValidationError, match="greater than 0"):
            RouteSuggestRequest(
                start_point={"lng": -122.33, "lat": 47.60},
                distance_meters=5000,
                city_id=1,
                neighborhood_id=0,
            )

    def test_neighborhood_id_none_is_ok(self):
        req = RouteSuggestRequest(
            start_point={"lng": -122.33, "lat": 47.60},
            distance_meters=5000,
            city_id=1,
            neighborhood_id=None,
        )
        assert req.neighborhood_id is None


class TestDatabasePostGIS:
    """Verify PostGIS initialization in database module."""

    def test_validate_postgis_function_exists(self):
        """Verify that _validate_postgis is importable from database module."""
        from app.database import _validate_postgis
        assert callable(_validate_postgis)

    def test_init_postgis_function_exists(self):
        """Verify that _init_postgis is importable from database module."""
        from app.database import _init_postgis
        assert callable(_init_postgis)


class TestImportStatusValues:
    """VALID_IMPORT_STATUSES includes error and gps_quality_warning."""

    def test_error_in_valid_statuses(self):
        from app.models.activity import Activity

        assert "error" in Activity.VALID_IMPORT_STATUSES

    def test_gps_quality_warning_in_valid_statuses(self):
        from app.models.activity import Activity

        assert "gps_quality_warning" in Activity.VALID_IMPORT_STATUSES

    def test_all_expected_statuses_present(self):
        from app.models.activity import Activity

        expected = {"pending", "polyline_imported", "streams_imported", "matched", "error", "gps_quality_warning"}
        assert Activity.VALID_IMPORT_STATUSES == expected


class TestSyncStatusValues:
    """VALID_SYNC_STATUSES includes complete."""

    def test_complete_in_valid_statuses(self):
        from app.models.user import User

        assert "complete" in User.VALID_SYNC_STATUSES

    def test_all_expected_statuses_present(self):
        from app.models.user import User

        expected = {"idle", "importing", "syncing", "complete", "error", "revoked"}
        assert User.VALID_SYNC_STATUSES == expected
