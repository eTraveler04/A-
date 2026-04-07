"""
Algorytm Dijkstry dla transportu publicznego.
"""
import heapq
import itertools

from models import (
    Connection,
    Cost,
    Graph,
    PathResult,
    SearchConfig,
    Seconds,
    State,
    StopId,
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


