"""
Tabu Search dla TSP na sieci kolejowej (Zadanie 2).

Warianty:
  (a) bazowy — tabu_size=None (nieograniczone T)
  (b) zmienny T — tabu_size='auto' → 2 * len(L)
  (c) aspiracja — aspiration=True
  (d) próbkowanie sąsiedztwa — sample_size=k
"""
import random
from collections import deque

from models import StopId, StopName
from dijkstra import search, make_time_config, make_transfers_config


# ---------------------------------------------------------------------------
# Ocena trasy
# ---------------------------------------------------------------------------

def evaluate_tour(
    tour_ids: list[set[StopId]],
    start_time: int,
    graph,
    criterion: str,
) -> tuple:
    """
    Oblicza koszt trasy przez sekwencyjne wywołania search().

    tour_ids: lista zbiorów stop_id, pierwszy == ostatni (start/koniec)
    Zwraca (koszt, wyniki) lub (inf, None) jeśli brak połączenia.
    Koszt: int (sekundy) dla 't', krotka (przesiadki, sekundy) dla 'p'.
    """
    current_time = start_time
    total_transfers = 0
    results = []

    for i in range(len(tour_ids) - 1):
        config = make_transfers_config() if criterion == 'p' else make_time_config()
        result, _ = search(graph, tour_ids[i], tour_ids[i + 1], current_time, config)

        if result is None:
            return float('inf'), None

        results.append(result)
        current_time = result.arrival_time

        if criterion == 'p':
            legs = result.legs
            transfers = sum(
                1 for j in range(1, len(legs))
                if legs[j].trip_id != legs[j - 1].trip_id
            )
            total_transfers += transfers

    if criterion == 'p':
        cost = (total_transfers, current_time - start_time)
    else:
        cost = current_time - start_time

    return cost, results


# ---------------------------------------------------------------------------
# Rozwiązanie początkowe — greedy
# ---------------------------------------------------------------------------

def greedy_initial(
    start_ids: set[StopId],
    candidates: list[tuple[StopName, set[StopId]]],
    start_time: int,
    graph,
) -> list[tuple[StopName, set[StopId]]]:
    """
    Buduje trasę startową zachłannie: zawsze jedź do najbliższego (czasowo)
    nieodwiedzonego przystanku.

    Zawsze używa kryterium czasu — to tylko punkt startowy dla Tabu Search.
    """
    remaining = list(candidates)
    ordered = []
    current_ids = start_ids
    current_time = start_time

    while remaining:
        best_arrival = float('inf')
        best_idx = None

        for idx, (_, ids) in enumerate(remaining):
            result, _ = search(graph, current_ids, ids, current_time, make_time_config())
            if result is not None and result.arrival_time < best_arrival:
                best_arrival = result.arrival_time
                best_idx = idx

        if best_idx is None:
            # brak połączenia — dołącz pozostałe w oryginalnej kolejności
            ordered.extend(remaining)
            break

        next_stop = remaining.pop(best_idx)
        ordered.append(next_stop)
        current_ids = next_stop[1]
        current_time = best_arrival

    return ordered


# ---------------------------------------------------------------------------
# Tabu Search
# ---------------------------------------------------------------------------

def tabu_search(
    start_name: StopName,
    start_ids: set[StopId],
    candidates: list[tuple[StopName, set[StopId]]],
    start_time: int,
    graph,
    criterion: str,
    max_iterations: int = 100,
    tabu_size=None,     # None = nieograniczone (a), int = stały (b), 'auto' = 2*n (b)
    aspiration: bool = False,   # wariant (c)
    sample_size=None,   # None = pełne sąsiedztwo, int = próbkowanie (d)
) -> tuple:
    """
    Tabu Search dla TSP na sieci kolejowej.

    Sąsiedztwo: swap dwóch przystanków pośrednich w trasie.
    Lista tabu: zbiory frozenset{name_i, name_j} ostatnio zamienionych przystanków.

    Zwraca (best_names, best_cost, best_results).
    """
    n = len(candidates)

    # Wariant (b): automatyczny rozmiar tablicy tabu
    if tabu_size == 'auto':
        tabu_size = 2 * n

    # --- rozwiązanie początkowe ---
    ordered = greedy_initial(start_ids, candidates, start_time, graph)

    cur_names = [start_name] + [name for name, _ in ordered] + [start_name]
    cur_ids   = [start_ids]  + [ids  for _, ids  in ordered] + [start_ids]

    cur_cost, cur_results = evaluate_tour(cur_ids, start_time, graph, criterion)

    best_names   = cur_names[:]
    best_ids     = cur_ids[:]
    best_cost    = cur_cost
    best_results = cur_results

    tabu: deque = deque()   # kolejka FIFO ruchów
    tabu_set: set = set()   # dla O(1) lookup

    for iteration in range(max_iterations):
        # wszystkie swappy pozycji pośrednich [1 .. n]
        all_swaps = [(i, j) for i in range(1, n + 1) for j in range(i + 1, n + 1)]

        # Wariant (d): próbkowanie sąsiedztwa
        if sample_size is not None and len(all_swaps) > sample_size:
            all_swaps = random.sample(all_swaps, sample_size)

        best_cand_cost    = None
        best_cand_swap    = None
        best_cand_names   = None
        best_cand_ids     = None
        best_cand_results = None

        for i, j in all_swaps:
            move = frozenset({cur_names[i], cur_names[j]})
            is_tabu = move in tabu_set

            # buduj sąsiada przez zamianę pozycji i oraz j
            nb_names = cur_names[:]
            nb_ids   = cur_ids[:]
            nb_names[i], nb_names[j] = nb_names[j], nb_names[i]
            nb_ids[i],   nb_ids[j]   = nb_ids[j],   nb_ids[i]

            cost, results = evaluate_tour(nb_ids, start_time, graph, criterion)
            if results is None:
                continue

            # Wariant (c): aspiracja — dopuść ruch tabu jeśli bije globalne optimum
            if is_tabu and aspiration and cost < best_cost:
                is_tabu = False

            if is_tabu:
                continue

            if best_cand_cost is None or cost < best_cand_cost:
                best_cand_cost    = cost
                best_cand_swap    = (i, j)
                best_cand_names   = nb_names
                best_cand_ids     = nb_ids
                best_cand_results = results

        if best_cand_swap is None:
            break  # brak dozwolonych ruchów

        # wykonaj najlepszy ruch
        i, j = best_cand_swap
        move = frozenset({cur_names[i], cur_names[j]})

        cur_names   = best_cand_names
        cur_ids     = best_cand_ids
        cur_cost    = best_cand_cost
        cur_results = best_cand_results

        # aktualizuj tablicę tabu (FIFO)
        tabu.append(move)
        tabu_set.add(move)
        if tabu_size is not None and len(tabu) > tabu_size:
            removed = tabu.popleft()
            tabu_set.discard(removed)

        # aktualizuj globalne optimum
        if cur_cost < best_cost:
            best_cost    = cur_cost
            best_names   = cur_names[:]
            best_ids     = cur_ids[:]
            best_results = cur_results

    return best_names, best_cost, best_results
