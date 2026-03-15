"""ORM models package — import all models here so Base.metadata is populated."""

from app.models.activity import Activity
from app.models.city import City
from app.models.coverage import CoverageSnapshot, UserStreetCoverage
from app.models.neighborhood import Neighborhood
from app.models.route import RouteSuggestion, RouteSuggestionSegment
from app.models.street import StreetSegment
from app.models.user import User

__all__ = [
    "Activity",
    "City",
    "CoverageSnapshot",
    "Neighborhood",
    "RouteSuggestion",
    "RouteSuggestionSegment",
    "StreetSegment",
    "User",
    "UserStreetCoverage",
]
