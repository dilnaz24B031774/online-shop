"""Order address -> (lat, lng) through OpenStreetMap Nominatim.

Free and without a key, but with a usage policy: at most one request per second,
an identifying User-Agent, and results should be cached. Every failure returns None,
so staff can always type the coordinates by hand instead.
"""
import hashlib
import json
import math
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from django.core.cache import cache

_lock = threading.Lock()
_last_call = 0.0
CACHE_SECONDS = 60 * 60 * 24 * 7


def _cache_key(address):
    return "geocode:" + hashlib.sha256(address.strip().lower().encode()).hexdigest()


# Nominatim does not understand most Russian street abbreviations, and flat numbers only confuse it.
_ABBREVIATIONS = (
    (r"\bпр-кт\.?|\bпр-т\.?|\bпросп\.|\bпр\.", "проспект "),
    (r"\bул\.", "улица "), (r"\bмкр-н\.?|\bмкрн?\.?(?=\s|\d)", "микрорайон "),
    (r"\bпер\.", "переулок "), (r"\bбул\.|\bб-р\.?", "бульвар "), (r"\bш\.", "шоссе "),
    (r"\bг\.\s*", ""), (r"\bд\.\s*", ""),
)
_NOISE = re.compile(r"(,?\s*\b(кв|квартира|офис|оф|подъезд|под|этаж|эт|apt|apartment|flat|office|entrance|floor)"
                    r"\b\.?\s*[\w-]*)", re.IGNORECASE)


def address_variants(address):
    """Cleaned-up queries, most precise first: full street address, then without the last part."""
    text = _NOISE.sub("", address)
    for pattern, replacement in _ABBREVIATIONS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    parts = [re.sub(r"\s+", " ", part).strip(" .") for part in text.split(",")]
    parts = [part for part in parts if part]
    variants = [", ".join(parts)] if parts else []
    if len(parts) > 2:                      # e.g. "Almaty, Abay Ave 10, building 3" -> drop the last part
        variants.append(", ".join(parts[:-1]))
    return [v for i, v in enumerate(variants) if v and v not in variants[:i]]


def geocode(address, country_codes="kz"):
    """Return (lat, lng) for an address, or None when it cannot be found."""
    address = (address or "").strip()
    if not address or not getattr(settings, "NOMINATIM_ENABLED", False):
        return None
    key = _cache_key(address)
    cached = cache.get(key)
    if cached is not None:
        return tuple(cached) if cached else None
    point, answered = None, False
    for query in address_variants(address):
        found = _lookup(query, country_codes)
        if found is _OFFLINE:
            break
        answered = True
        if found:
            point = found
            break
    if answered:                             # offline: do not cache, try again later
        cache.set(key, list(point) if point else [], CACHE_SECONDS)
    return point


_OFFLINE = object()


def _lookup(query_text, country_codes):
    """One Nominatim request: (lat, lng), None when nothing matched, or _OFFLINE on a network error."""
    address = query_text
    query = urllib.parse.urlencode({"q": address, "format": "jsonv2", "limit": 1,
                                    "countrycodes": country_codes, "accept-language": "ru"})
    request = urllib.request.Request(f"{settings.NOMINATIM_URL}?{query}",
                                     headers={"User-Agent": settings.NOMINATIM_USER_AGENT})
    global _last_call
    try:
        with _lock:                                   # one request per second, as the policy asks
            wait = 1.0 - (time.monotonic() - _last_call)
            if wait > 0:
                time.sleep(wait)
            _last_call = time.monotonic()
            with urllib.request.urlopen(request, timeout=5) as response:
                results = json.load(response)
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return _OFFLINE
    point = None
    if isinstance(results, list) and results:
        try:
            lat, lng = float(results[0]["lat"]), float(results[0]["lon"])
            if math.isfinite(lat) and math.isfinite(lng) and abs(lat) <= 90 and abs(lng) <= 180:
                point = (round(lat, 6), round(lng, 6))
        except (KeyError, TypeError, ValueError):
            point = None
    return point


def distance_m(lat1, lng1, lat2, lng2):
    """Great-circle distance in metres."""
    lat1, lng1, lat2, lng2 = map(math.radians, (float(lat1), float(lng1), float(lat2), float(lng2)))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(h))
