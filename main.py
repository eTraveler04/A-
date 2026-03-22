"""
Wyszukiwarka połączeń Kolei Dolnośląskich.

Użycie:
    python3 main.py
"""
import time
from datetime import date

from gtfs_loader import (
    Graph,
    Seconds,
    StopId,
    StopName,
    build_graph,
    load_active_service_ids,
    load_active_trip_ids,
    load_connections,
    load_stops,
    load_stops_by_name,
    load_trip_to_route,
    time_to_seconds,
)
from dijkstra import PathResult, dijkstra, print_result


def main() -> None:
    print("Wczytywanie danych...")
    stops: dict[StopId, StopName] = load_stops()
    stops_by_name: dict[StopName, list[StopId]] = load_stops_by_name()
    route_names: dict[str, str] = load_trip_to_route()
    active_services = load_active_service_ids(date.today())
    active_trips = load_active_trip_ids(active_services)
    connections = load_connections(active_trips)
    graph: Graph = build_graph(connections)
    print("Gotowe.\n")

    from_name: str = input("Skąd: ").strip()
    to_name: str = input("Dokąd: ").strip()
    time_str: str = input("Najwcześniejszy odjazd (HH:MM): ").strip()

    source_ids: set[StopId] = set(stops_by_name.get(from_name, []))
    target_ids: set[StopId] = set(stops_by_name.get(to_name, []))

    if not source_ids:
        print(f"Nie znaleziono przystanku: {from_name}")
        return
    if not target_ids:
        print(f"Nie znaleziono przystanku: {to_name}")
        return

    earliest_departure: Seconds = time_to_seconds(time_str + ":00")

    t0: float = time.perf_counter()
    result: PathResult | None = dijkstra(graph, source_ids, target_ids, earliest_departure)
    computation_time: float = time.perf_counter() - t0

    if result:
        print_result(result, stops, route_names, computation_time)
    else:
        print("Brak połączenia.")


if __name__ == "__main__":
    main()
