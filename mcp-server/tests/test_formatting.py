"""Tests for pure formatting functions and helpers in server.py."""

from pacman_mcp.server import _format_city_coverage, _progress_bar


class TestProgressBar:
    def test_zero(self):
        assert _progress_bar(0) == "[----------]"

    def test_hundred(self):
        assert _progress_bar(100) == "[##########]"

    def test_fifty(self):
        assert _progress_bar(50) == "[#####-----]"

    def test_partial(self):
        assert _progress_bar(73) == "[#######---]"

    def test_custom_width(self):
        assert _progress_bar(50, width=4) == "[##--]"


class TestFormatCityCoverage:
    def test_basic_output(self):
        cov = {
            "city": {
                "name": "Seattle",
                "coverage_percentage": 42.5,
                "streets_traveled": 21250,
                "streets_total": 50000,
                "distance_traveled_m": 850000.0,
                "distance_total_m": 2000000.0,
            },
            "neighborhoods": [
                {"name": "Fremont", "coverage_percentage": 73.2, "streets_traveled": 366, "streets_total": 500},
                {"name": "Capitol Hill", "coverage_percentage": 45.0, "streets_traveled": 360, "streets_total": 800},
            ],
        }
        result = _format_city_coverage(cov)
        assert "Seattle" in result
        assert "42.5%" in result
        assert "21,250 / 50,000" in result
        assert "850.0 km / 2000.0 km" in result
        assert "Fremont" in result
        assert "Capitol Hill" in result

    def test_neighborhoods_sorted_by_coverage_desc(self):
        cov = {
            "city": {
                "name": "Test", "coverage_percentage": 50, "streets_traveled": 50,
                "streets_total": 100, "distance_traveled_m": 1000, "distance_total_m": 2000,
            },
            "neighborhoods": [
                {"name": "Low", "coverage_percentage": 10.0, "streets_traveled": 10, "streets_total": 100},
                {"name": "High", "coverage_percentage": 90.0, "streets_traveled": 90, "streets_total": 100},
                {"name": "Mid", "coverage_percentage": 50.0, "streets_traveled": 50, "streets_total": 100},
            ],
        }
        result = _format_city_coverage(cov)
        high_pos = result.index("High")
        mid_pos = result.index("Mid")
        low_pos = result.index("Low")
        assert high_pos < mid_pos < low_pos

    def test_milestone_proximity(self):
        cov = {
            "city": {
                "name": "Test", "coverage_percentage": 23.0, "streets_traveled": 230,
                "streets_total": 1000, "distance_traveled_m": 5000, "distance_total_m": 20000,
            },
            "neighborhoods": [],
        }
        result = _format_city_coverage(cov)
        assert "25%" in result
        assert "20 more streets" in result

    def test_no_milestone_at_100(self):
        cov = {
            "city": {
                "name": "Done", "coverage_percentage": 100.0, "streets_traveled": 1000,
                "streets_total": 1000, "distance_traveled_m": 20000, "distance_total_m": 20000,
            },
            "neighborhoods": [],
        }
        result = _format_city_coverage(cov)
        assert "milestone" not in result.lower()
