"""Distance and geocoding. Google Routes/Geocoding when a key is set, straight-line otherwise."""
import math
from typing import Protocol

import httpx
from fastapi import HTTPException

from ..config import get_settings


class MapsError(Exception):
    pass


class MapsProvider(Protocol):
    def route_meters(self, o_lat: float, o_lng: float, d_lat: float, d_lng: float, mode: str) -> int: ...
    def geocode(self, query: str) -> tuple[float, float] | None: ...


class GoogleMapsProvider:
    def __init__(self):
        self.key = get_settings().google_maps_api_key
        if not self.key:
            raise MapsError("Google Maps key not configured")

    def route_meters(self, o_lat, o_lng, d_lat, d_lng, mode):
        body = {"origin": {"location": {"latLng": {"latitude": o_lat, "longitude": o_lng}}},
                "destination": {"location": {"latLng": {"latitude": d_lat, "longitude": d_lng}}},
                "travelMode": mode}
        try:
            r = httpx.post("https://routes.googleapis.com/directions/v2:computeRoutes", json=body, timeout=10,
                           headers={"X-Goog-Api-Key": self.key, "X-Goog-FieldMask": "routes.distanceMeters"})
            data = r.json()
            return int(data["routes"][0]["distanceMeters"])
        except (httpx.HTTPError, ValueError, KeyError, IndexError):
            raise MapsError("Google route lookup failed")

    def geocode(self, query):
        try:
            r = httpx.get("https://maps.googleapis.com/maps/api/geocode/json",
                          params={"address": query, "region": "gh", "key": self.key}, timeout=10)
            res = r.json().get("results") or []
        except (httpx.HTTPError, ValueError):
            raise MapsError("Google geocoding failed")
        if not res:
            return None
        loc = res[0]["geometry"]["location"]
        return float(loc["lat"]), float(loc["lng"])


_factory = GoogleMapsProvider


def get_maps() -> MapsProvider:
    return _factory()


def set_maps_factory(f):  # tests
    global _factory
    _factory = f


def haversine_meters(a_lat, a_lng, b_lat, b_lng) -> int:
    r = 6371000.0
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dp, dl = p2 - p1, math.radians(b_lng - a_lng)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return int(round(2 * r * math.asin(math.sqrt(h))))
