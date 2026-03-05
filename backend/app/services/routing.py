from __future__ import annotations

import math
from typing import List, Tuple

from app.models.schemas import GPS


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    # Earth radius in km
    r = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


def build_route_nearest_neighbor(start: GPS, stops: List[GPS]) -> Tuple[List[int], float]:
    """
    Returns (order_indices, total_distance_km) using a nearest-neighbor heuristic.
    """
    if not stops:
        return ([], 0.0)

    remaining = list(range(len(stops)))
    order: List[int] = []
    total = 0.0
    cur = start

    while remaining:
        best_i = None
        best_d = None
        for idx in remaining:
            d = haversine_km(cur.lat, cur.lon, stops[idx].lat, stops[idx].lon)
            if best_d is None or d < best_d:
                best_d = d
                best_i = idx

        assert best_i is not None and best_d is not None
        order.append(best_i)
        total += best_d
        cur = stops[best_i]
        remaining.remove(best_i)

    return (order, total)