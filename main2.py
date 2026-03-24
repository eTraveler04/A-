"""
Wyszukiwarka trasy TSP na sieci Kolei Dolnośląskich (Zadanie 2).

Użycie:
    python main2.py "Wrocław Główny" "Legnica;Jelenia Góra" t "08:30" "pon"
    python main2.py "Wrocław Główny" "Legnica;Jelenia Góra" t "08:30" "pon" --tabu-size auto
    python main2.py "Wrocław Główny" "Legnica;Jelenia Góra" p "08:30" "pon" --aspiration
    python main2.py "Wrocław Główny" "Legnica;Jelenia Góra" t "08:30" "pon" --sample 5
"""
import sys
import time
from datetime import date, timedelta
from itertools import groupby

from gtfs_loader import (
    load_stops,
    load_stops_by_name,
    load_active_service_ids,
    load_active_trip_ids,
    load_connections,
    load_trip_to_route,
    build_graph,
    seconds_to_time,
    time_to_seconds,
)
from tabu import tabu_search
from utils import parse_day


def print_tsp_result(best_names, best_cost, best_results, stops, route_names, criterion, computation_time):
    """Wypisuje wynik trasy TSP: szczegóły każdego odcinka i zbiorcze podsumowanie."""
    print(f"Trasa: {' → '.join(best_names)}\n")

    total_start = best_results[0].departure_time if best_results else 0
    total_end   = best_results[-1].arrival_time  if best_results else 0

    for leg_idx, result in enumerate(best_results):
        from_name = stops.get(result.from_stop_id, result.from_stop_id)
        to_name   = stops.get(result.to_stop_id,   result.to_stop_id)
        print(f"Odcinek {leg_idx + 1}: {from_name} → {to_name}")

        for trip_id, group in groupby(result.legs, key=lambda c: c.trip_id):
            segments = list(group)
            seg_from = stops.get(segments[0].from_stop_id, segments[0].from_stop_id)
            seg_to   = stops.get(segments[-1].to_stop_id,  segments[-1].to_stop_id)
            route    = route_names.get(trip_id, trip_id)
            dep      = seconds_to_time(segments[0].departure_time)
            arr      = seconds_to_time(segments[-1].arrival_time)
            print(f"  {seg_from} → {seg_to}  [{route}]  {dep} → {arr}")
        print()

    # podsumowanie
    total_sec = total_end - total_start
    days, rem = divmod(total_sec, 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60

    total_transfers = sum(
        sum(1 for i in range(1, len(r.legs)) if r.legs[i].trip_id != r.legs[i - 1].trip_id)
        for r in best_results
    )

    print(f"Odjazd:          {seconds_to_time(total_start)}")
    print(f"Przyjazd:        {seconds_to_time(total_end)}")
    print(f"Czas całkowity:  {days:02d}:{hours:02d}:{minutes:02d}")
    print(f"Przesiadki:      {total_transfers}")

    # stderr
    if criterion == 'p':
        print(best_cost[0], file=sys.stderr)
    else:
        print(seconds_to_time(total_end), file=sys.stderr)
    print(f"{computation_time:.3f}s", file=sys.stderr)


def main() -> None:
    print("Wczytywanie danych...")
    stops        = load_stops()
    stops_by_name = load_stops_by_name()
    route_names  = load_trip_to_route()
    print("Gotowe.\n")

    raw_args = sys.argv[1:]

    # wydziel flagi (--xxx) od argumentów pozycyjnych
    pos_args = [a for a in raw_args if not a.startswith('--')]
    flag_args = raw_args  # zachowujemy pełną listę do wyszukiwania flag

    if len(pos_args) >= 4:
        from_name   = pos_args[0]
        stops_str   = pos_args[1]
        criterion   = pos_args[2]
        time_str    = pos_args[3]
        travel_date = parse_day(pos_args[4]) if len(pos_args) >= 5 else date.today()
    else:
        from_name   = input("Skąd (przystanek startowy): ").strip()
        stops_str   = input("Lista przystanków (oddzielone ;): ").strip()
        criterion   = input("Kryterium (t = czas, p = przesiadki): ").strip()
        time_str    = input("Najwcześniejszy odjazd (HH:MM): ").strip()
        day_str     = input("Dzień tygodnia [domyślnie: dziś]: ").strip()
        travel_date = parse_day(day_str) if day_str else date.today()

    # --- flagi wariantów ---
    tabu_size   = None
    aspiration  = '--aspiration' in flag_args
    sample_size = None

    if '--tabu-size' in flag_args:
        idx = flag_args.index('--tabu-size')
        val = flag_args[idx + 1]
        tabu_size = 'auto' if val == 'auto' else int(val)

    if '--sample' in flag_args:
        idx = flag_args.index('--sample')
        sample_size = int(flag_args[idx + 1])

    # --- rozwiązywanie nazw przystanków ---
    start_ids = set(stops_by_name.get(from_name, []))
    if not start_ids:
        print(f"Nie znaleziono przystanku: {from_name}")
        return

    stop_names = [s.strip() for s in stops_str.split(';')]

    # usuń duplikaty i przystanek startowy z listy (zachowaj kolejność)
    seen = {from_name}
    unique_stop_names = []
    for name in stop_names:
        if name not in seen:
            seen.add(name)
            unique_stop_names.append(name)
    stop_names = unique_stop_names

    if not stop_names:
        print("Lista przystanków do odwiedzenia jest pusta po usunięciu duplikatów.")
        return

    candidates = []
    for name in stop_names:
        ids = set(stops_by_name.get(name, []))
        if not ids:
            print(f"Nie znaleziono przystanku: {name}")
            return
        candidates.append((name, ids))

    earliest = time_to_seconds(time_str + ":00")

    # --- wczytanie grafu ---
    active_services  = load_active_service_ids(travel_date)
    active_trips     = load_active_trip_ids(active_services)
    connections      = load_connections(active_trips)

    next_day_services = load_active_service_ids(travel_date + timedelta(days=1))
    next_day_trips    = load_active_trip_ids(next_day_services)
    connections      += load_connections(next_day_trips, time_offset=86400)

    graph = build_graph(connections)

    # --- Tabu Search ---
    t0 = time.perf_counter()
    best_names, best_cost, best_results = tabu_search(
        from_name, start_ids, candidates, earliest, graph, criterion,
        tabu_size=tabu_size,
        aspiration=aspiration,
        sample_size=sample_size,
    )
    computation_time = time.perf_counter() - t0

    if best_results is None:
        print("Brak połączenia.")
        return

    print_tsp_result(best_names, best_cost, best_results, stops, route_names, criterion, computation_time)


if __name__ == "__main__":
    main()
