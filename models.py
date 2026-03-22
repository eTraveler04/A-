"""
Wspólne typy i klasy danych używane w całym projekcie.
"""
from dataclasses import dataclass

StopId = str
StopName = str
TripId = str
ServiceId = str
Seconds = int  # czas jako liczba sekund od północy

Graph = dict[StopId, list["Connection"]]


@dataclass(frozen=True)
class StopVisit:
    """Pojedyncze zatrzymanie kursu na przystanku."""
    sequence: int
    stop_id: StopId
    arrival_time: Seconds
    departure_time: Seconds


@dataclass(frozen=True)
class Connection:
    """Odcinek kursu między dwoma kolejnymi przystankami."""
    trip_id: TripId
    from_stop_id: StopId
    to_stop_id: StopId
    departure_time: Seconds
    arrival_time: Seconds


@dataclass
class PathResult:
    """Wynik wyszukiwania trasy."""
    from_stop_name: StopName
    to_stop_name: StopName
    departure_time: Seconds
    arrival_time: Seconds
    legs: list[Connection]  # kolejne odcinki trasy
