"""
Wyszukiwarka połączeń Kolei Dolnośląskich.

Użycie:
    python3 main.py
    python3 main.py "Wrocław Główny" "Legnica" t "08:30" "poniedzialek"
    python3 main.py "Wrocław Główny" "Legnica" p "08:30" "1"   # 1=pon, 7=nie
"""
import sys
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
    load_stop_coords,
    load_trip_to_route,
    time_to_seconds,
)
from dijkstra import search, make_time_config, make_transfers_config, print_result, PathResult
from visualize import visualize
from utils import parse_day


def main() -> None:
    print("Wczytywanie danych...")
    stops: dict[StopId, StopName] = load_stops()
    stops_by_name: dict[StopName, list[StopId]] = load_stops_by_name()
    coords = load_stop_coords()
    route_names: dict[str, str] = load_trip_to_route()
    print("Gotowe.\n")

    args = sys.argv[1:]
    if len(args) >= 4:
        from_name, to_name, criterion, time_str = args[0], args[1], args[2], args[3]
        travel_date = parse_day(args[4]) if len(args) >= 5 else date.today()
    else:
        from_name = input("Skąd: ").strip()
        to_name = input("Dokąd: ").strip()
        criterion = input("Kryterium (t = czas, p = przesiadki): ").strip()
        time_str = input("Najwcześniejszy odjazd (HH:MM): ").strip()
        day_str = input("Dzień tygodnia [domyślnie: dziś]: ").strip()
        travel_date = parse_day(day_str) if day_str else date.today()

    source_ids: set[StopId] = set(stops_by_name.get(from_name, []))
    target_ids: set[StopId] = set(stops_by_name.get(to_name, []))

    if not source_ids:
        print(f"Nie znaleziono przystanku: {from_name}")
        return
    if not target_ids:
        print(f"Nie znaleziono przystanku: {to_name}")
        return

    earliest_departure: Seconds = time_to_seconds(time_str + ":00")

    active_services = load_active_service_ids(travel_date)
    active_trips = load_active_trip_ids(active_services)
    connections = load_connections(active_trips)
    graph: Graph = build_graph(connections)

    config = make_transfers_config() if criterion == "p" else make_time_config()

    t0: float = time.perf_counter()
    result: PathResult | None = search(graph, source_ids, target_ids, earliest_departure, config)
    computation_time: float = time.perf_counter() - t0

    if result:
        print_result(result, stops, route_names, computation_time, criterion)
        visualize(result, stops, coords, route_names)
    else:
        print("Brak połączenia.")


if __name__ == "__main__":
    main()
