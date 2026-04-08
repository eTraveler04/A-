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
    Generyczny algorytm Dijkstry / A* — kryterium optymalizacji definiuje SearchConfig.

    State to aktualny węzeł (np. stop_id lub (stop_id, trip_id)).
    Cost to aktualny koszt dotarcia do stanu (np. czas przybycia lub (przesiadki, czas)).
    f = cost + h(state) to priorytet w kolejce (dla zwykłej Dijkstry f = cost).

    prev przechowuje (poprzedni_stan, połączenie) zamiast samego połączenia,
    żeby rekonstrukcja ścieżki działała dla dowolnego typu stanu.
    """
    h = config.heuristic

    best_cost: dict[State, Cost] = {}  # najlepszy znany koszt dotarcia do każdego stanu
    prev: dict[State, tuple[State, Connection] | None] = {}  # skąd dotarliśmy do danego stanu
    queue: list = []  # min-heap: (f, counter, cost, state)
    counter = itertools.count()  # unikalny tiebreaker — unika porównywania stanów w heapie
    step = 0  # licznik odwiedzonych węzłów (do statystyk)

    # inicjalizacja: wrzuć wszystkie przystanki startowe do kolejki
    for cost, state in config.initial_states(source_ids, departure_time):
        best_cost[state] = cost
        prev[state] = None  # None oznacza węzeł startowy (brak poprzednika)
        if h:
            # A*: priorytet f = koszt rzeczywisty + oszacowanie do celu
            h_val = h(state)
            f = config.make_f(cost, h_val) if config.make_f else cost + h_val
        else:
            # zwykła Dijkstra: priorytet = koszt rzeczywisty
            f = cost
        heapq.heappush(queue, (f, next(counter), cost, state))

    while queue:
        # wyciągnij stan z najniższym priorytetem f
        current_f, _, current_cost, current_state = heapq.heappop(queue)

        # lazy deletion: w heapie mogą być starsze wpisy dla tego samego stanu z wyższym kosztem
        # (wrzucone zanim znaleźliśmy lepszą ścieżkę) — jeśli koszt się nie zgadza, pomijamy
        if current_cost != best_cost.get(current_state):
            continue

        step += 1
        if config.on_visit:
            current_h = h(current_state) if h else 0
            # opcjonalny callback np. do trybu --verbose
            config.on_visit(step, current_state, current_cost, current_h, current_f)

        if config.is_goal(current_state, target_ids):
            return _build_result(current_state, prev, best_cost, departure_time, config), step

        # rozwiń sąsiadów: każde połączenie wychodzące z obecnego przystanku
        for new_cost, new_state, conn in config.expand(current_state, current_cost, graph):
            if new_state not in best_cost or new_cost < best_cost[new_state]:
                # znaleźliśmy lepszą ścieżkę do new_state — zaktualizuj i wrzuć do kolejki
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
    """Odtwarza ścieżkę cofając się po prev od celu do źródła, potem odwraca."""
    legs: list[Connection] = []
    current: State = target_state

    while prev[current] is not None:
        prev_state, conn = prev[current]  # type: ignore[misc]
        legs.append(conn)
        current = prev_state

    legs.reverse()  # odcinki były dodawane od końca, teraz odwracamy do naturalnej kolejności

    return PathResult(
        from_stop_id=config.get_stop_id(current),
        to_stop_id=config.get_stop_id(target_state),
        departure_time=legs[0].departure_time if legs else departure_time,
        arrival_time=config.get_arrival_time(best_cost[target_state]),
        legs=legs,
    )
