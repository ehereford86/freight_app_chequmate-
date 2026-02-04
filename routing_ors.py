from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from typing import Optional, Tuple, Dict, Any

import db

ORS_KEY_ENV = "ORS_API_KEY"
ORS_BASE = "https://api.openrouteservice.org"


def _read_http_error(e: Exception) -> str:
    try:
        import urllib.error
        if isinstance(e, urllib.error.HTTPError):
            body = e.read()
            try:
                txt = body.decode("utf-8", errors="replace")
            except Exception:
                txt = repr(body)
            txt = (txt or "").strip()
            if len(txt) > 900:
                txt = txt[:900] + "..."
            return txt
    except Exception:
        pass
    return ""


def _http_json(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 12.0,
    method: str = "GET",
    body: Optional[dict] = None,
) -> Any:
    data = None
    hdrs = dict(headers or {})

    if body is not None:
        raw = json.dumps(body).encode("utf-8")
        data = raw
        hdrs.setdefault("Content-Type", "application/json")

    req = urllib.request.Request(url, headers=hdrs, method=method, data=data)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return json.loads(raw)
    except Exception as e:
        body_txt = _read_http_error(e)
        if body_txt:
            raise RuntimeError(f"{e} | {body_txt}") from e
        raise


def _ors_key() -> str:
    key = (os.environ.get(ORS_KEY_ENV) or "").strip()
    if not key:
        raise RuntimeError(f"Missing {ORS_KEY_ENV}. Export it in your shell before starting the server.")
    return key


def _normalize_zip(z: str) -> str:
    z = (z or "").strip()
    digits = "".join(ch for ch in z if ch.isdigit())
    if len(digits) >= 5:
        return digits[:5]
    return digits


def _zippopotam_us(zip_code: str) -> Tuple[Optional[Tuple[float, float]], Dict[str, Any]]:
    """
    Reliable US ZIP geocoder (no API key).
    https://api.zippopotam.us/us/{zip}
    Returns (lon, lat).
    """
    z = _normalize_zip(zip_code)
    if not z:
        return None, {"ok": False, "error": "Bad ZIP", "source": "input"}

    url = f"https://api.zippopotam.us/us/{z}"
    headers = {"User-Agent": "chequmate-freight-app/1.0 (local-dev)"}

    try:
        j = _http_json(url, headers=headers, timeout=10.0, method="GET")
        places = (j or {}).get("places") or []
        if not places:
            return None, {"ok": False, "error": "ZIP not found", "source": "zippopotam", "zip": z, "url": url}

        p = places[0]
        lat = float(p.get("latitude"))
        lon = float(p.get("longitude"))
        meta = {
            "ok": True,
            "source": "zippopotam",
            "zip": z,
            "country": "US",
            "place_name": p.get("place name"),
            "state": p.get("state"),
            "state_abbreviation": p.get("state abbreviation"),
        }
        return (lon, lat), meta
    except Exception as e:
        return None, {"ok": False, "error": str(e), "source": "zippopotam", "zip": z, "url": url}


def _nominatim_geocode_zip(zip_code: str, country: str = "US") -> Tuple[Optional[Tuple[float, float]], Dict[str, Any]]:
    z = _normalize_zip(zip_code)
    country = (country or "US").strip().upper()
    if not z:
        return None, {"ok": False, "error": "Bad ZIP", "source": "input"}

    params = {
        "format": "json",
        "limit": 1,
        "postalcode": z,
        "countrycodes": country.lower(),
        "addressdetails": 0,
    }
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(params)
    headers = {"User-Agent": "chequmate-freight-app/1.0 (contact: local-dev)"}

    try:
        j = _http_json(url, headers=headers, timeout=12.0, method="GET")
        if not isinstance(j, list) or not j:
            return None, {"ok": False, "error": "ZIP not found", "source": "nominatim", "zip": z, "country": country, "url": url}

        item = j[0]
        lat = float(item.get("lat"))
        lon = float(item.get("lon"))
        return (lon, lat), {"ok": True, "source": "nominatim", "zip": z, "country": country}
    except Exception as e:
        return None, {"ok": False, "error": str(e), "source": "nominatim", "zip": z, "country": country, "url": url}


def geocode_zip(zip_code: str, country: str = "US") -> Tuple[Optional[Tuple[float, float]], Dict[str, Any]]:
    """
    Returns ((lon, lat), meta). Cached in DB.

    US:
      - Zippopotam.us (reliable ZIP → coords)
      - fallback Nominatim
    Non-US:
      - ORS/Pelias then Nominatim
    """
    z = _normalize_zip(zip_code)
    country = (country or "US").strip().upper()

    if not z:
        return None, {"ok": False, "error": "Bad ZIP", "source": "input"}

    # cache
    try:
        cached = db.get_geocode_cache(z, country)
        if cached:
            return (float(cached["lon"]), float(cached["lat"])), {
                "ok": True,
                "source": "cache",
                "zip": z,
                "country": country,
                "cached_at": cached.get("created_at"),
            }
    except Exception:
        pass

    if country == "US":
        coords, meta = _zippopotam_us(z)
        if coords:
            try:
                db.set_geocode_cache(z, country, coords[0], coords[1])
            except Exception:
                pass
            return coords, meta

        coords2, meta2 = _nominatim_geocode_zip(z, country=country)
        if coords2:
            try:
                db.set_geocode_cache(z, country, coords2[0], coords2[1])
            except Exception:
                pass
            return coords2, meta2

        return None, meta

    # Non-US: ORS/Pelias
    key = _ors_key()
    headers = {"Authorization": key}

    def _try_ors(params: dict) -> Tuple[Optional[Tuple[float, float]], Dict[str, Any]]:
        url = f"{ORS_BASE}/geocode/search?{urllib.parse.urlencode(params)}"
        try:
            j = _http_json(url, headers=headers, timeout=12.0, method="GET")
            feats = j.get("features") or []
            if not feats:
                return None, {"ok": False, "error": "ZIP not found", "source": "ors_geocode", "zip": z, "country": country, "url": url}

            geom = feats[0].get("geometry") or {}
            coords = geom.get("coordinates")
            if not coords or len(coords) < 2:
                return None, {"ok": False, "error": "Bad geocode response", "source": "ors_geocode", "zip": z, "country": country, "url": url}

            lon, lat = float(coords[0]), float(coords[1])
            return (lon, lat), {"ok": True, "source": "ors_geocode", "zip": z, "country": country}
        except Exception as e:
            return None, {"ok": False, "error": str(e), "source": "ors_geocode", "zip": z, "country": country, "url": url}

    coords, meta = _try_ors({
        "text": f"{z} {country}",
        "size": 1,
        "layers": "postalcode",
        "boundary.country": country,
    })
    if coords:
        try:
            db.set_geocode_cache(z, country, coords[0], coords[1])
        except Exception:
            pass
        return coords, meta

    coords2, meta2 = _try_ors({
        "text": f"{z} {country}",
        "size": 1,
        "boundary.country": country,
    })
    if coords2:
        try:
            db.set_geocode_cache(z, country, coords2[0], coords2[1])
        except Exception:
            pass
        return coords2, meta2

    coords3, meta3 = _nominatim_geocode_zip(z, country=country)
    if coords3:
        try:
            db.set_geocode_cache(z, country, coords3[0], coords3[1])
        except Exception:
            pass
        return coords3, meta3

    return None, meta


def route_miles_zip_to_zip(origin_zip: str, dest_zip: str, country: str = "US") -> Tuple[Optional[float], Optional[float], Dict[str, Any]]:
    """
    Returns (miles, seconds, meta). Cached in DB.
    Uses ORS directions GeoJSON endpoint so response has 'features'.
    """
    oz = _normalize_zip(origin_zip)
    dz = _normalize_zip(dest_zip)
    country = (country or "US").strip().upper()

    if not oz or not dz:
        return None, None, {"ok": False, "error": "Bad ZIP(s)", "source": "input", "origin_zip": oz, "dest_zip": dz}

    # cache
    try:
        cached = db.get_mileage_cache(oz, dz, provider="ors", country=country)
        if cached:
            return float(cached["miles"]), float(cached["seconds"]), {
                "ok": True,
                "source": "cache",
                "provider": "ors",
                "origin_zip": oz,
                "dest_zip": dz,
                "country": country,
                "cached_at": cached.get("created_at"),
            }
    except Exception:
        pass

    (o, o_meta) = geocode_zip(oz, country=country)
    if not o:
        return None, None, {"ok": False, "error": "Origin geocode failed", "source": "ors", "origin": o_meta, "dest_zip": dz}

    (d, d_meta) = geocode_zip(dz, country=country)
    if not d:
        return None, None, {"ok": False, "error": "Dest geocode failed", "source": "ors", "origin_zip": oz, "dest": d_meta}

    key = _ors_key()

    # IMPORTANT: geojson endpoint returns 'features' (what our parser expects)
    url = f"{ORS_BASE}/v2/directions/driving-car/geojson"
    headers = {"Authorization": key}

    body = {
        "coordinates": [[o[0], o[1]], [d[0], d[1]]],
        "radiuses": [5000, 5000],
    }

    try:
        j = _http_json(url, headers=headers, timeout=18.0, method="POST", body=body)

        feats = (j or {}).get("features") or []
        if not feats:
            # include more context if ORS returns a non-geojson error structure
            err = (j or {}).get("error") if isinstance(j, dict) else None
            return None, None, {
                "ok": False,
                "error": "No route found",
                "source": "ors_directions",
                "origin_zip": oz,
                "dest_zip": dz,
                "origin_coords": o,
                "dest_coords": d,
                "ors_error": err,
            }

        props = (feats[0].get("properties") or {})
        summ = (props.get("summary") or {})
        dist_m = float(summ.get("distance") or 0.0)
        dur_s = float(summ.get("duration") or 0.0)

        miles = float(round(dist_m / 1609.344, 2))
        dur_s = float(round(dur_s, 0))

        try:
            db.set_mileage_cache(oz, dz, provider="ors", country=country, miles=miles, seconds=dur_s)
        except Exception:
            pass

        return miles, dur_s, {
            "ok": True,
            "source": "ors_directions",
            "provider": "ors",
            "origin_zip": oz,
            "dest_zip": dz,
            "country": country,
            "origin_geocode": o_meta,
            "dest_geocode": d_meta,
        }
    except Exception as e:
        return None, None, {"ok": False, "error": str(e), "source": "ors_directions", "origin_zip": oz, "dest_zip": dz}
