"""
Algorytm Dijkstry dla transportu publicznego.

Użycie:
    python3 dijkstra.py
"""
import heapq
import itertools
import sys
from dataclasses import dataclass
from datetime import date
from itertools import groupby
from typing import Any, Callable

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

# State i Cost to dowolne porównywalne typy — konkretne znaczenie zależy od SearchConfig
State = Any
Cost = Any


@dataclass
class SearchConfig:
    """
    Konfiguracja wyszukiwania — definiuje kryterium optymalizacji.

    initial_states  -- (source_ids, departure_time) -> [(cost, state), ...]
    expand          -- (state, cost, graph) -> [(new_cost, new_state, conn), ...]
    is_goal         -- (state, target_ids) -> bool
    get_stop_id     -- state -> StopId
    get_arrival_time-- cost -> Seconds  (do PathResult)
    """
    initial_states: Callable[[set[StopId], Seconds], list[tuple[Cost, State]]]
    expand: Callable[[State, Cost, Graph], list[tuple[Cost, State, Connection]]]
    is_goal: Callable[[State, set[StopId]], bool]
    get_stop_id: Callable[[State], StopId]
    get_arrival_time: Callable[[Cost], Seconds]


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


def search(
    graph: Graph,
    source_ids: set[StopId],
    target_ids: set[StopId],
    departure_time: Seconds,
    config: SearchConfig,
) -> PathResult | None:
    """
    Generyczny algorytm Dijkstry — kryterium optymalizacji definiuje SearchConfig.

    prev przechowuje (poprzedni_stan, połączenie) zamiast samego połączenia,
    żeby rekonstrukcja ścieżki działała dla dowolnego typu stanu.
    """
    best_cost: dict[State, Cost] = {}
    prev: dict[State, tuple[State, Connection] | None] = {}
    queue: list = []
    counter = itertools.count()  # tiebreaker — unika porównywania stanów w heapie

    for cost, state in config.initial_states(source_ids, departure_time):
        best_cost[state] = cost
        prev[state] = None
        heapq.heappush(queue, (cost, next(counter), state))

    while queue:
        current_cost, _, current_state = heapq.heappop(queue)

        # wpis zdezaktualizowany — znaleźliśmy już lepszą ścieżkę do tego stanu
        if current_cost != best_cost.get(current_state):
            continue

        if config.is_goal(current_state, target_ids):
            return _build_result(current_state, prev, best_cost, departure_time, config)

        for new_cost, new_state, conn in config.expand(current_state, current_cost, graph):
            if new_state not in best_cost or new_cost < best_cost[new_state]:
                best_cost[new_state] = new_cost
                prev[new_state] = (current_state, conn)
                heapq.heappush(queue, (new_cost, next(counter), new_state))

    return None


def _build_result(
    target_state: State,
    prev: dict[State, tuple[State, Connection] | None],
    best_cost: dict[State, Cost],
    departure_time: Seconds,
    config: SearchConfig,
) -> PathResult:
    """Odtwarza ścieżkę cofając się po prev."""
    legs: list[Connection] = []
    current: State = target_state

    while prev[current] is not None:
        prev_state, conn = prev[current]  # type: ignore[misc]
        legs.append(conn)
        current = prev_state

    legs.reverse()

    return PathResult(
        from_stop_name=config.get_stop_id(current),
        to_stop_name=config.get_stop_id(target_state),
        departure_time=legs[0].departure_time if legs else departure_time,
        arrival_time=config.get_arrival_time(best_cost[target_state]),
        legs=legs,
    )


def print_result(
    result: PathResult,
    stops: dict[StopId, StopName],
    route_names: dict[str, str],
    computation_time: float,
    criterion: str = "t",
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

    from_stop: StopName = stops.get(result.from_stop_name, result.from_stop_name)
    to_stop: StopName = stops.get(result.to_stop_name, result.to_stop_name)

    print()
    print(f"Trasa:       {from_stop} → {to_stop}")
    print(f"Odjazd:      {seconds_to_time(dep_time)}")
    print(f"Przyjazd:    {seconds_to_time(arr_time)}")
    print(f"Czas:        {days:02d}:{hours:02d}:{minutes:02d}")
    print(f"Przesiadki:  {transfers}")
    print(f"Linie:       {lines}")

    # --- stderr: wartość kryterium + czas obliczenia ---
    if criterion == "t":
        print(seconds_to_time(arr_time), file=sys.stderr)
    else:
        print(transfers, file=sys.stderr)
    print(f"{computation_time:.3f}s", file=sys.stderr)
