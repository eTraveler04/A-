"""
Fabryki konfiguracji wyszukiwania (SearchConfig) dla różnych kryteriów optymalizacji.
"""
import heapq
import math
from collections import defaultdict

from models import Connection, Graph, SearchConfig, Seconds, StopId, TripId


def make_time_config() -> SearchConfig:
    """Kryterium: minimalizacja czasu przybycia. Stan = stop_id."""
    return SearchConfig(
        initial_states=lambda source_ids, t: [(t, sid) for sid in source_ids],
        expand=lambda state, cost, graph: [
            (conn.arrival_time, conn.to_stop_id, conn)
            for conn in graph.get(state, [])
            if conn.departure_time >= cost
        ],
        is_goal=lambda state, target_ids: state in target_ids,
        get_stop_id=lambda state: state,
        get_arrival_time=lambda cost: cost,
    )


def make_transfers_config() -> SearchConfig:
    """
    Kryterium: minimalizacja liczby przesiadek. Stan = (stop_id, trip_id).
    Koszt = (liczba_przesiadek, czas_przybycia) — leksykograficznie:
    najpierw minimalizuj przesiadki, przy remisie minimalizuj czas.
    """
    def expand(state: tuple, cost: tuple, graph: Graph) -> list:
        stop_id, current_trip = state
        num_transfers, current_time = cost
        result = []
        for conn in graph.get(stop_id, []):
            if conn.departure_time < current_time:
                continue
            is_transfer = current_trip is not None and conn.trip_id != current_trip
            new_cost = (num_transfers + (1 if is_transfer else 0), conn.arrival_time)
            result.append((new_cost, (conn.to_stop_id, conn.trip_id), conn))
        return result

    return SearchConfig(
        initial_states=lambda source_ids, t: [((0, t), (sid, None)) for sid in source_ids],
        expand=expand,
        is_goal=lambda state, target_ids: state[0] in target_ids,
        get_stop_id=lambda state: state[0],
        get_arrival_time=lambda cost: cost[1],
    )


def make_astar_time_euclidean_config(
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

    def heuristic(state: StopId) -> Seconds:
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


def make_astar_time_reverse_dijkstra_config(
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

    def heuristic(state: StopId) -> Seconds:
        # Zwraca 0 jeśli brak danych — bezpieczne (heurystyka trywialna)
        return dist.get(state, 0)

    config = make_time_config()
    config.heuristic = heuristic
    return config


def make_astar_transfers_direct_trip_config(
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

    def heuristic(state: tuple) -> int:
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


def make_astar_transfers_bfs_config(
    graph: Graph,
    target_ids: set[StopId],
) -> SearchConfig:
    """
    Kryterium: minimalizacja liczby przesiadek — algorytm A* z ulepszoną heurystyką.
    Heurystyka: minimalna liczba przesiadek z obecnego kursu do celu,
    obliczona przez BFS po grafie przesiadek (kursy dzielące przystanek).
    """
    from collections import deque

    # Krok 1: indeksy — dla każdego przystanku jakie kursy się tam zatrzymują,
    # i dla każdego kursu na jakich przystankach się zatrzymuje
    stop_to_trips: dict[StopId, set[TripId]] = defaultdict(set)
    trip_to_stops: dict[TripId, set[StopId]] = defaultdict(set)
    for conns in graph.values():
        for conn in conns:
            stop_to_trips[conn.from_stop_id].add(conn.trip_id)
            trip_to_stops[conn.trip_id].add(conn.from_stop_id)

    # Krok 2: BFS od kursów docierających do celu
    min_transfers: dict[TripId, int] = {}
    queue: deque = deque()

    for conns in graph.values():
        for conn in conns:
            if conn.to_stop_id in target_ids and conn.trip_id not in min_transfers:
                min_transfers[conn.trip_id] = 0
                queue.append(conn.trip_id)

    while queue:
        trip = queue.popleft()
        d = min_transfers[trip]
        # dla każdego przystanku kursu sprawdź kursy z którymi można się przesiąść
        for stop_id in trip_to_stops[trip]:
            for other_trip in stop_to_trips[stop_id]:
                if other_trip not in min_transfers:
                    min_transfers[other_trip] = d + 1
                    queue.append(other_trip)

    def heuristic(state: tuple) -> int:
        stop_id, trip_id = state
        if stop_id in target_ids:
            return 0
        if trip_id is None:
            for conn in graph.get(stop_id, []):
                if min_transfers.get(conn.trip_id, 1) == 0:
                    return 0
            return 1
        return min_transfers.get(trip_id, 1)

    config = make_transfers_config()
    config.heuristic = heuristic
    config.make_f = lambda cost, h: (cost[0] + h, cost[1])
    return config
