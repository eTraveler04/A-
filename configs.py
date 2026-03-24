"""
Fabryki konfiguracji wyszukiwania (SearchConfig) dla różnych kryteriów optymalizacji.
"""
import heapq
import math
from collections import defaultdict

from models import Connection, Graph, Seconds, StopId
from dijkstra import SearchConfig, make_time_config, make_transfers_config


def make_astar_time_config(
    coords: dict[StopId, tuple[float, float]],
    target_ids: set[StopId],
    max_speed_ms: float = 44.4,  # ~160 km/h — górna granica prędkości, heurystyka dopuszczalna
) -> SearchConfig:
    """
    Kryterium: minimalizacja czasu przybycia — algorytm A*.
    Heurystyka: odległość euklidesowa do najbliższego przystanku docelowego / max_speed_ms.
    """
    target_coords: list[tuple[float, float]] = [
        coords[sid] for sid in target_ids if sid in coords
    ]

    def heuristic(state: StopId, _target_ids: set[StopId]) -> Seconds:
        if state not in coords or not target_coords:
            return 0
        lat1, lon1 = coords[state]
        min_dist = min(
            math.sqrt(
                ((lat2 - lat1) * 111_320) ** 2
                + ((lon2 - lon1) * 111_320 * math.cos(math.radians((lat1 + lat2) / 2))) ** 2
            )
            for lat2, lon2 in target_coords
        )
        return int(min_dist / max_speed_ms)

    config = make_time_config()
    config.heuristic = heuristic
    return config


def make_astar_time_improved_config(
    graph: Graph,
    target_ids: set[StopId],
) -> SearchConfig:
    """
    Kryterium: minimalizacja czasu przybycia — algorytm A* z ulepszoną heurystyką.
    Heurystyka: odwrócona Dijkstra od celu na uproszczonym grafie (minimalne czasy przejazdu,
    bez uwzględniania rozkładu jazdy). Daje dolne ograniczenie rzeczywistego czasu przejazdu.
    """
    # Minimalne czasy przejazdu między przystankami (ignorujemy rozkład)
    min_travel: dict[tuple[StopId, StopId], int] = {}
    for conns in graph.values():
        for conn in conns:
            key = (conn.from_stop_id, conn.to_stop_id)
            t = conn.arrival_time - conn.departure_time
            if key not in min_travel or t < min_travel[key]:
                min_travel[key] = t

    # Odwrócony graf: to_stop -> [(from_stop, min_travel_time)]
    rev: dict[StopId, list[tuple[StopId, int]]] = defaultdict(list)
    for (from_stop, to_stop), t in min_travel.items():
        rev[to_stop].append((from_stop, t))

    # Dijkstra wstecz od celu
    dist: dict[StopId, int] = {}
    queue: list = []
    for tid in target_ids:
        dist[tid] = 0
        heapq.heappush(queue, (0, tid))

    while queue:
        d, v = heapq.heappop(queue)
        if d > dist.get(v, float("inf")):
            continue
        for u, t in rev.get(v, []):
            nd = d + t
            if nd < dist.get(u, float("inf")):
                dist[u] = nd
                heapq.heappush(queue, (nd, u))

    def heuristic(state: StopId, _target_ids: set[StopId]) -> Seconds:
        # Zwraca 0 jeśli brak danych — bezpieczne (heurystyka trywialna)
        return dist.get(state, 0)

    config = make_time_config()
    config.heuristic = heuristic
    return config


def make_astar_transfers_config(
    graph: Graph,
    target_ids: set[StopId],
) -> SearchConfig:
    """
    Kryterium: minimalizacja liczby przesiadek — algorytm A*.
    Heurystyka: 0 jeśli obecny kurs dociera do celu, 1 w przeciwnym razie.
    """
    trips_to_target: set[str] = set()
    for connections in graph.values():
        for conn in connections:
            if conn.to_stop_id in target_ids:
                trips_to_target.add(conn.trip_id)

    def heuristic(state: tuple, _target_ids: set[StopId]) -> int:
        stop_id, trip_id = state
        if stop_id in target_ids:
            return 0
        if trip_id is not None and trip_id in trips_to_target:
            return 0
        return 1

    config = make_transfers_config()
    config.heuristic = heuristic
    config.make_f = lambda cost, h: (cost[0] + h, cost[1])
    return config
