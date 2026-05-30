from math import asin, cos, radians, sin, sqrt


def haversine_distance_m(lat1: float, lng1: float, lat2: float, lng2: float) -> int:
    radius_m = 6_371_000
    lat1_r, lng1_r, lat2_r, lng2_r = map(radians, [lat1, lng1, lat2, lng2])
    dlat = lat2_r - lat1_r
    dlng = lng2_r - lng1_r
    a = sin(dlat / 2) ** 2 + cos(lat1_r) * cos(lat2_r) * sin(dlng / 2) ** 2
    return int(2 * radius_m * asin(sqrt(a)))
