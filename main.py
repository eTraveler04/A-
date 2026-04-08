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

from itertools import groupby

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
    seconds_to_time,
    time_to_seconds,
)
from models import PathResult
from dijkstra import search
from configs import (
    make_time_config,
    make_transfers_config,
    make_astar_time_euclidean_config,
    make_astar_time_reverse_dijkstra_config,
    make_astar_transfers_direct_trip_config,
    make_astar_transfers_bfs_config,
)
from visualize import visualize
from utils import parse_day


def print_result(
    result: PathResult,
    stops: dict[StopId, StopName],
    route_names: dict[str, str],
    computation_time: float,
    criterion: str = "t",
    visited_nodes: int = 0,
) -> None:
    # --- odcinki (jeden wiersz per kurs) ---
    for trip_id, group in groupby(result.legs, key=lambda c: c.trip_id):
        segments = list(group)
        from_name: StopName = stops.get(segments[0].from_stop_id, segments[0].from_stop_id)
        to_name: StopName = stops.get(segments[-1].to_stop_id, segments[-1].to_stop_id)
        route: str = route_names.get(trip_id, trip_id)
        dep: str = seconds_to_time(segments[0].departure_time)
        arr: str = seconds_to_time(segments[-1].arrival_time)
        print(f"{from_name} → {to_name}  [{route}]  {dep} → {arr}")

    # --- podsumowanie ---
    dep_time: Seconds = result.departure_time
    arr_time: Seconds = result.arrival_time
    total_sec: int = arr_time - dep_time
    hours, remainder = divmod(total_sec, 3600)
    minutes = remainder // 60
    days, hours = divmod(hours, 24)

    transfers: int = sum(
        1 for i in range(1, len(result.legs))
        if result.legs[i].trip_id != result.legs[i - 1].trip_id
    )
    lines: list[str] = list(dict.fromkeys(
        route_names.get(leg.trip_id, leg.trip_id) for leg in result.legs
    ))

    from_stop: StopName = stops.get(result.from_stop_id, result.from_stop_id)
    to_stop: StopName = stops.get(result.to_stop_id, result.to_stop_id)

    print()
    print(f"Trasa:       {from_stop} → {to_stop}")
    print(f"Odjazd:      {seconds_to_time(dep_time)}")
    print(f"Przyjazd:    {seconds_to_time(arr_time)}")
    print(f"Czas:        {days:02d}:{hours:02d}:{minutes:02d}")
    print(f"Przesiadki:  {transfers}")
    print(f"Linie:       {lines}")
    print(f"Odwiedzone węzły: {visited_nodes}")

    # --- stderr: wartość kryterium + czas obliczenia ---
    if criterion in ("t", "at", "ats"):
        print(seconds_to_time(arr_time), file=sys.stderr)
    else:
        print(transfers, file=sys.stderr)
    print(f"{computation_time:.3f}s", file=sys.stderr)


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
        criterion = input("Kryterium (t = czas, p = przesiadki, at = A* czas, ats = A* czas ulepsz., ap = A* przesiadki, aps = A* przesiadki ulepsz.): ").strip()
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

    if criterion == "aps":
        config = make_astar_transfers_bfs_config(graph, target_ids)
    elif criterion == "ap":
        config = make_astar_transfers_direct_trip_config(graph, target_ids)
    elif criterion == "p":
        config = make_transfers_config()
    elif criterion == "at":
        config = make_astar_time_euclidean_config(coords, target_ids)
    elif criterion == "ats":
        config = make_astar_time_reverse_dijkstra_config(graph, target_ids)
    else:
        config = make_time_config()

    if verbose:
        def on_visit(step: int, state, cost, h_val, f) -> None:
            stop_id = state if isinstance(state, str) else state[0]
            trip_id = None if isinstance(state, str) else state[1]
            name = stops.get(stop_id, stop_id)
            arrival = seconds_to_time(cost if isinstance(cost, int) else cost[1])
            transfers = "" if isinstance(cost, int) else f"  przesiadki_g={cost[0]}"
            trip_str = f"  kurs={trip_id}" if trip_id else ""
            print(f"  [{step:>4}] {name:<35} przybycie: {arrival}  h={h_val}  f={f}{transfers}{trip_str}", file=sys.stderr)
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
