"""QR code generation utility for location-bound maintenance QR codes.

Each QR code encodes a URL containing:
- equipment_id: unique identifier for the equipment
- lat/lng: the GPS coordinates where the QR code is placed
- radius: maximum allowed distance (metres) from the QR location
"""

import base64
import io
import math
import urllib.parse

import qrcode


def generate_qr_code(base_url, equipment_id, latitude, longitude, radius_m=100):
    """Generate a QR code image that encodes a location-bound maintenance URL.

    Parameters
    ----------
    base_url : str
        The base URL of the maintenance application
        (e.g. ``"http://localhost:8050"``).
    equipment_id : str
        Unique identifier for the equipment / asset.
    latitude : float
        Latitude where the QR code will be placed.
    longitude : float
        Longitude where the QR code will be placed.
    radius_m : int
        Maximum distance in metres from ``(latitude, longitude)`` within which
        scanning is allowed.  Defaults to 100 m.

    Returns
    -------
    tuple[str, str]
        A ``(qr_url, qr_base64)`` pair where *qr_url* is the encoded URL and
        *qr_base64* is the PNG image as a base-64 data-URI string.
    """
    params = urllib.parse.urlencode({
        "equipment_id": equipment_id,
        "lat": f"{latitude:.6f}",
        "lng": f"{longitude:.6f}",
        "radius": str(int(radius_m)),
    })
    qr_url = f"{base_url}/maintenance?{params}"

    img = qrcode.make(qr_url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    encoded = base64.b64encode(buf.read()).decode("utf-8")
    qr_base64 = f"data:image/png;base64,{encoded}"

    return qr_url, qr_base64


def haversine_distance(lat1, lon1, lat2, lon2):
    """Return the great-circle distance in metres between two GPS points."""
    R = 6_371_000  # Earth radius in metres
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def verify_location(user_lat, user_lng, qr_lat, qr_lng, radius_m=100):
    """Check whether the user is within the allowed radius of the QR location.

    Returns
    -------
    tuple[bool, float]
        ``(is_within_radius, distance_m)``
    """
    distance = haversine_distance(user_lat, user_lng, qr_lat, qr_lng)
    return distance <= radius_m, round(distance, 2)
