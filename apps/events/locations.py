"""
Location tag helpers for Editor's Pick scoping.

Location tags represent editorial scopes, not strict geographic boundaries.
Bounding boxes cover metro areas and are used to derive a tag from GPS coordinates.
"""

LOCATION_BOUNDS = {
    'nairobi': {'lat_min': -1.45, 'lat_max': -1.15, 'lng_min': 36.65, 'lng_max': 37.05},
    'mombasa': {'lat_min': -4.10, 'lat_max': -3.95, 'lng_min': 39.55, 'lng_max': 39.75},
    'kisumu': {'lat_min': -0.15, 'lat_max': -0.05, 'lng_min': 34.70, 'lng_max': 34.80},
    'naivasha': {'lat_min': -0.78, 'lat_max': -0.65, 'lng_min': 36.40, 'lng_max': 36.55},
    'nakuru': {'lat_min': -0.35, 'lat_max': -0.25, 'lng_min': 36.05, 'lng_max': 36.15},
    'diani': {'lat_min': -4.40, 'lat_max': -4.25, 'lng_min': 39.55, 'lng_max': 39.65},
}


def location_tag_from_coords(lat, lng):
    """
    Return the location_tag matching given GPS coords, or 'nairobi' as fallback.

    Args:
        lat: Latitude (float or None)
        lng: Longitude (float or None)

    Returns:
        str: Location tag (e.g., 'nairobi', 'mombasa')
    """
    if lat is None or lng is None:
        return 'nairobi'

    for tag, bounds in LOCATION_BOUNDS.items():
        if (bounds['lat_min'] <= lat <= bounds['lat_max']
                and bounds['lng_min'] <= lng <= bounds['lng_max']):
            return tag

    return 'nairobi'  # default fallback


def get_location_tag_choices():
    """Return location tag choices for Django admin select widget."""
    return [(tag, tag.title()) for tag in sorted(LOCATION_BOUNDS.keys())]
