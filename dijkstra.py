"""
Algorytm Dijkstry dla transportu publicznego.
Koszt = czas przybycia (najwcześniejsze dotarcie do celu).

Stan w kolejce: (czas_przybycia, stop_id)

Użycie:
    python3 dijkstra.py
"""
import heapq
from datetime import date

from models import (
    Connection,
    Graph,
    PathResult,
    Seconds,
    StopId,
    StopName,
)
from gtfs_loader import (
    seconds_to_time,
    load_stops,
    load_stops_by_name,
    load_active_service_ids,
    load_active_trip_ids,
    load_connections,
    build_graph,
)


def dijkstra(
    graph: Graph,
    source_ids: set[StopId],
    target_ids: set[StopId],
    earliest_departure: Seconds,
) -> PathResult | None:
    """
    Szuka najwcześniejszego dotarcia z dowolnego source_id do dowolnego target_id.

    graph             - graf sąsiedztwa zbudowany przez build_graph()
    source_ids        - wszystkie stop_id przystanku startowego
    target_ids        - wszystkie stop_id przystanku docelowego
    earliest_departure - najwcześniejszy odjazd (sekundy od północy)
    """
    # best_arrival[stop_id] = najlepszy znany czas przybycia
    best_arrival: dict[StopId, Seconds] = {}

    # poprzednik: stop_id -> Connection którą tu dotarliśmy
    prev: dict[StopId, Connection | None] = {}

    # kolejka: (czas_przybycia, stop_id)
    queue: list[tuple[Seconds, StopId]] = []

    # inicjalizacja — wszystkie perony przystanku startowego
    for sid in source_ids:
        best_arrival[sid] = earliest_departure
        prev[sid] = None
        heapq.heappush(queue, (earliest_departure, sid))

    while queue:
        current_time: Seconds
        current_stop: StopId
        current_time, current_stop = heapq.heappop(queue)

        # pominięcie zdezaktualizowanych wpisów w kolejce
        if current_time > best_arrival.get(current_stop, current_time + 1):
            continue

        # cel osiągnięty
        if current_stop in target_ids:
            return _build_result(current_stop, prev, best_arrival, earliest_departure)

        for conn in graph.get(current_stop, []):
            # kurs musi odjeżdżać nie wcześniej niż jesteśmy na przystanku
            if conn.departure_time < current_time:
                continue

            if conn.arrival_time < best_arrival.get(conn.to_stop_id, float("inf")):
                best_arrival[conn.to_stop_id] = conn.arrival_time
                prev[conn.to_stop_id] = conn
                heapq.heappush(queue, (conn.arrival_time, conn.to_stop_id))

    return None  # brak połączenia


def _build_result(
    target_stop: StopId,
    prev: dict[StopId, Connection | None],
    best_arrival: dict[StopId, Seconds],
    departure_time: Seconds,
) -> PathResult:
    """Odtwarza ścieżkę cofając się po prev."""
    legs: list[Connection] = []
    current: StopId = target_stop

    while prev.get(current) is not None:
        conn: Connection = prev[current]  # type: ignore[assignment]
        legs.append(conn)
        current = conn.from_stop_id

    legs.reverse()

    return PathResult(
        from_stop_name=current,
        to_stop_name=target_stop,
        departure_time=legs[0].departure_time if legs else departure_time,
        arrival_time=best_arrival[target_stop],
        legs=legs,
    )


def print_result(
    result: PathResult,
    stops: dict[StopId, StopName],
    route_names: dict[str, str],
    computation_time: float,
) -> None:
    import sys
    from itertools import groupby

    # Grupowanie odcinków po trip_id → jeden wiersz na stdout per kurs
    for trip_id, group in groupby(result.legs, key=lambda c: c.trip_id):
        segments = list(group)
        from_name: StopName = stops.get(segments[0].from_stop_id, segments[0].from_stop_id)
        to_name: StopName = stops.get(segments[-1].to_stop_id, segments[-1].to_stop_id)
        route: str = route_names.get(trip_id, trip_id)
        dep: str = seconds_to_time(segments[0].departure_time)
        arr: str = seconds_to_time(segments[-1].arrival_time)
        print(f"{from_name},{to_name},{route},{dep},{arr}")

    # stderr: wartość kryterium (czas przybycia) + czas obliczenia
    print(seconds_to_time(result.arrival_time), file=sys.stderr)
    print(f"{computation_time:.3f}s", file=sys.stderr)
