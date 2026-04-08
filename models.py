"""
Wspólne typy i klasy danych używane w całym projekcie.
"""
from dataclasses import dataclass
from typing import Any, Callable

StopId = str
StopName = str
TripId = str
ServiceId = str
Seconds = int  # czas jako liczba sekund od północy

Graph = dict[StopId, list["Connection"]]


@dataclass(frozen=True)
class StopTimeRow:
    """Pojedyncze zatrzymanie kursu na przystanku."""
    sequence: int
    stop_id: StopId
    arrival_time: Seconds
    departure_time: Seconds
    pickup_type: int = 0    # 0 = regularne wsiadanie, 1 = brak wsiadania


@dataclass(frozen=True)
class Connection:
    """Odcinek kursu między dwoma kolejnymi przystankami.  Jest to krawędź w grafie połączeń."""
    trip_id: TripId
    from_stop_id: StopId
    to_stop_id: StopId
    departure_time: Seconds
    arrival_time: Seconds


@dataclass
class PathResult:
    """Wynik wyszukiwania trasy."""
    from_stop_id: StopId
    to_stop_id: StopId
    departure_time: Seconds
    arrival_time: Seconds
    legs: list[Connection]  # kolejne odcinki trasy


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
    heuristic: Callable[[State], Any] | None = None
    make_f: Callable[[Cost, Any], Any] | None = None
    on_visit: Callable[[int, State, Cost, Any, Any], None] | None = None  # step, state, cost, h_val, f
