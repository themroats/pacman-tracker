"""Unit tests for GPX export service."""

import datetime
import xml.etree.ElementTree as ET

from geoalchemy2.shape import from_shape
from shapely.geometry import LineString, Point

from app.services.gpx_export import build_gpx


class _FakeSuggestion:
    """Minimal stand-in for RouteSuggestion without a real DB session."""

    def __init__(self, coords, distance=5000.0, duration=2500, untraveled_ratio=0.6):
        self.route_geometry = from_shape(LineString(coords), srid=4326)
        self.start_point = from_shape(Point(coords[0]), srid=4326)
        self.distance_meters = distance
        self.estimated_duration_seconds = duration
        self.untraveled_distance_meters = distance * untraveled_ratio
        self.untraveled_ratio = untraveled_ratio
        self.created_at = datetime.datetime(2026, 3, 28, 12, 0, 0, tzinfo=datetime.timezone.utc)


class TestBuildGpx:
    """Tests for build_gpx()."""

    COORDS = [
        (-122.33, 47.60),
        (-122.34, 47.61),
        (-122.35, 47.62),
        (-122.34, 47.63),
        (-122.33, 47.60),  # round-trip
    ]

    def _parse(self, xml_str: str) -> ET.Element:
        return ET.fromstring(xml_str)

    def test_returns_valid_xml(self):
        suggestion = _FakeSuggestion(self.COORDS)
        gpx_xml = build_gpx(suggestion)
        root = self._parse(gpx_xml)
        assert root.tag.endswith("gpx")

    def test_contains_track_with_correct_point_count(self):
        suggestion = _FakeSuggestion(self.COORDS)
        gpx_xml = build_gpx(suggestion)
        root = self._parse(gpx_xml)
        ns = {"g": "http://www.topografix.com/GPX/1/1"}
        trkpts = root.findall(".//g:trk/g:trkseg/g:trkpt", ns)
        assert len(trkpts) == len(self.COORDS)

    def test_trackpoint_coordinates_match(self):
        suggestion = _FakeSuggestion(self.COORDS)
        gpx_xml = build_gpx(suggestion)
        root = self._parse(gpx_xml)
        ns = {"g": "http://www.topografix.com/GPX/1/1"}
        trkpts = root.findall(".//g:trk/g:trkseg/g:trkpt", ns)
        # First point: lng=-122.33, lat=47.60
        assert float(trkpts[0].attrib["lat"]) == 47.60
        assert float(trkpts[0].attrib["lon"]) == -122.33

    def test_contains_metadata_name(self):
        suggestion = _FakeSuggestion(self.COORDS)
        gpx_xml = build_gpx(suggestion)
        root = self._parse(gpx_xml)
        ns = {"g": "http://www.topografix.com/GPX/1/1"}
        name = root.find(".//g:metadata/g:name", ns)
        assert name is not None
        assert "Pacman Route" in name.text

    def test_contains_start_end_waypoints(self):
        suggestion = _FakeSuggestion(self.COORDS)
        gpx_xml = build_gpx(suggestion)
        root = self._parse(gpx_xml)
        ns = {"g": "http://www.topografix.com/GPX/1/1"}
        wpts = root.findall("g:wpt", ns)
        names = [w.find("g:name", ns).text for w in wpts]
        assert "Start" in names
        assert "End" in names

    def test_description_contains_stats(self):
        suggestion = _FakeSuggestion(self.COORDS, distance=5000.0, untraveled_ratio=0.6)
        gpx_xml = build_gpx(suggestion)
        root = self._parse(gpx_xml)
        ns = {"g": "http://www.topografix.com/GPX/1/1"}
        desc = root.find(".//g:metadata/g:desc", ns)
        assert desc is not None
        assert "5.0 km" in desc.text
        assert "60%" in desc.text

    def test_two_point_route(self):
        """Minimal route with just 2 coordinates."""
        coords = [(-122.33, 47.60), (-122.34, 47.61)]
        suggestion = _FakeSuggestion(coords)
        gpx_xml = build_gpx(suggestion)
        root = self._parse(gpx_xml)
        ns = {"g": "http://www.topografix.com/GPX/1/1"}
        trkpts = root.findall(".//g:trk/g:trkseg/g:trkpt", ns)
        assert len(trkpts) == 2
        wpts = root.findall("g:wpt", ns)
        assert len(wpts) == 2
