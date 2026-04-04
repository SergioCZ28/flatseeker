import time
from datetime import datetime, timedelta

import requests

from flatseeker.config import GOOGLE_MAPS_API_KEY, TARGET_ADDRESS


def _next_weekday_8am() -> int:
    """Return Unix timestamp for next Monday at 8:00 AM CET."""
    now = datetime.now()
    days_ahead = 7 - now.weekday()  # Monday = 0
    if days_ahead == 7:
        days_ahead = 0
    next_monday = now + timedelta(days=days_ahead)
    departure = next_monday.replace(hour=8, minute=0, second=0, microsecond=0)
    if departure < now:
        departure += timedelta(weeks=1)
    return int(departure.timestamp())


def get_transit_time(origin_address: str) -> int | None:
    """
    Get transit time in minutes from origin to the configured target address.
    Returns None if API call fails or no transit route found.
    """
    if not GOOGLE_MAPS_API_KEY:
        print("  [WARN] No Google Maps API key configured")
        return None

    if not origin_address or len(origin_address) < 5:
        return None

    # Ensure address includes Basel if it doesn't already
    if "Basel" not in origin_address and "basel" not in origin_address:
        origin_address += ", Basel, Switzerland"

    url = "https://maps.googleapis.com/maps/api/directions/json"
    params = {
        "origin": origin_address,
        "destination": TARGET_ADDRESS,
        "mode": "transit",
        "departure_time": _next_weekday_8am(),
        "key": GOOGLE_MAPS_API_KEY,
    }

    try:
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()

        if data["status"] == "OK" and data["routes"]:
            duration_sec = data["routes"][0]["legs"][0]["duration"]["value"]
            return duration_sec // 60

        # Fallback: try walking if transit fails
        params["mode"] = "walking"
        del params["departure_time"]
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()

        if data["status"] == "OK" and data["routes"]:
            duration_sec = data["routes"][0]["legs"][0]["duration"]["value"]
            return duration_sec // 60

    except Exception as e:
        print(f"  [WARN] Maps API error for '{origin_address}': {e}")

    return None


def get_transit_time_cached(origin_address: str, cache: dict) -> int | None:
    """Check cache first, then call API. Updates cache in-place."""
    cache_key = f"transit:{origin_address}"
    if cache_key in cache:
        return cache[cache_key]

    # Be polite to the API
    time.sleep(0.3)
    result = get_transit_time(origin_address)
    cache[cache_key] = result
    return result
