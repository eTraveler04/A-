"""
Wyszukiwarka połączeń Kolei Dolnośląskich.

Użycie:
    python3 main.py
    python3 main.py "Wrocław Główny" "Legnica" t "08:30" "poniedzialek"
    python3 main.py "Wrocław Główny" "Legnica" p "08:30" "1"   # 1=pon, 7=nie
    python3 main.py "Wrocław Główny" "Legnica" t "08:30" "1" --verbose
"""
import sys
import time
from datetime import date, timedelta

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
from dijkstra import search, make_time_config, make_transfers_config, make_astar_transfers_config, make_astar_time_config, print_result
from visualize import visualize
from utils import parse_day


def main() -> None:
    print("Wczytywanie danych...")
    stops: dict[StopId, StopName] = load_stops()
    stops_by_name: dict[StopName, list[StopId]] = load_stops_by_name()
    coords = load_stop_coords()
    route_names: dict[str, str] = load_trip_to_route()
    print("Gotowe.\n")

    args = [a for a in sys.argv[1:] if a != "--verbose"]
    verbose = "--verbose" in sys.argv

    if len(args) >= 4:
        from_name, to_name, criterion, time_str = args[0], args[1], args[2], args[3]
        travel_date = parse_day(args[4]) if len(args) >= 5 else date.today()
    else:
        from_name = input("Skąd: ").strip()
        to_name = input("Dokąd: ").strip()
        criterion = input("Kryterium (t = czas, p = przesiadki, at = A* czas, ap = A* przesiadki): ").strip()
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

    next_day_services = load_active_service_ids(travel_date + timedelta(days=1))
    next_day_trips = load_active_trip_ids(next_day_services)
    connections += load_connections(next_day_trips, time_offset=86400)

    graph: Graph = build_graph(connections)

    if criterion == "ap":
        config = make_astar_transfers_config(graph, target_ids)
    elif criterion == "p":
        config = make_transfers_config()
    elif criterion == "at":
        config = make_astar_time_config(coords, target_ids)
    else:
        config = make_time_config()

    if verbose:
        from gtfs_loader import seconds_to_time
        def on_visit(step: int, state, cost) -> None:
            stop_id = state if isinstance(state, str) else state[0]
            name = stops.get(stop_id, stop_id)
            arrival = seconds_to_time(cost if isinstance(cost, int) else cost[1])
            print(f"  [{step:>4}] {name:<35} przybycie: {arrival}", file=sys.stderr)
        config.on_visit = on_visit

    t0: float = time.perf_counter()
    result, visited_nodes = search(graph, source_ids, target_ids, earliest_departure, config)
    computation_time: float = time.perf_counter() - t0

    if result:
        print_result(result, stops, route_names, computation_time, criterion, visited_nodes)
        visualize(result, stops, coords, route_names)
    else:
        print("Brak połączenia.")


if __name__ == "__main__":
    main()
