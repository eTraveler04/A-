"""
Algorytm Dijkstry dla transportu publicznego.
"""
import heapq
import itertools
import sys
from itertools import groupby

from models import (
    Connection,
    Cost,
    Graph,
    PathResult,
    SearchConfig,
    Seconds,
    State,
    StopId,
    StopName,
)
from gtfs_loader import seconds_to_time


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
    h = config.heuristic

    best_cost: dict[State, Cost] = {}
    prev: dict[State, tuple[State, Connection] | None] = {}
    queue: list = []
    counter = itertools.count()  # tiebreaker — unika porównywania stanów w heapie
    step = 0

    for cost, state in config.initial_states(source_ids, departure_time):
        best_cost[state] = cost
        prev[state] = None
        if h:
            h_val = h(state)
            f = config.make_f(cost, h_val) if config.make_f else cost + h_val
        else:
            f = cost
        heapq.heappush(queue, (f, next(counter), cost, state))

    while queue:
        _, _, current_cost, current_state = heapq.heappop(queue)

        # wpis zdezaktualizowany — znaleźliśmy już lepszą ścieżkę do tego stanu
        if current_cost != best_cost.get(current_state):
            continue

        step += 1
        if config.on_visit:
            config.on_visit(step, current_state, current_cost)

        if config.is_goal(current_state, target_ids):
            return _build_result(current_state, prev, best_cost, departure_time, config), step

        for new_cost, new_state, conn in config.expand(current_state, current_cost, graph):
            if new_state not in best_cost or new_cost < best_cost[new_state]:
                best_cost[new_state] = new_cost
                prev[new_state] = (current_state, conn)
                if h:
                    h_val = h(new_state)
                    new_f = config.make_f(new_cost, h_val) if config.make_f else new_cost + h_val
                else:
                    new_f = new_cost
                heapq.heappush(queue, (new_f, next(counter), new_cost, new_state))

    return None, step


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
        from_stop_id=config.get_stop_id(current),
        to_stop_id=config.get_stop_id(target_state),
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
