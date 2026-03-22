"""
Funkcje pomocnicze przygotowujące dane GTFS do algorytmu Dijkstry.

Stan w algorytmie: (czas_przybycia, stop_id)
Krawędź: Connection(from_stop, to_stop, departure_time, arrival_time, trip_id)

Czasy przechowywane jako sekundy od północy (int), bo GTFS dopuszcza
wartości > 24:00:00 dla kursów po północy (np. 25:30:00).
"""
import csv
from datetime import date
from pathlib import Path
from collections import defaultdict

from models import (
    Connection,
    Graph,
    Seconds,
    ServiceId,
    StopId,
    StopName,
    StopVisit,
    TripId,
)

GTFS_DIR: Path = Path(__file__).parent / "google_transit"


def time_to_seconds(time_str: str) -> Seconds:
    """Zamienia 'HH:MM:SS' na liczbę sekund od północy. Obsługuje > 24h."""
    h, m, s = time_str.split(":")
    return int(h) * 3600 + int(m) * 60 + int(s)


def seconds_to_time(seconds: Seconds) -> str:
    """Zamienia sekundy od północy na 'HH:MM:SS'."""
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02}:{m:02}:{s:02}"


def load_stops() -> dict[StopId, StopName]:
    """Zwraca mapę stop_id -> stop_name (tylko fizyczne przystanki)."""
    stops: dict[StopId, StopName] = {}
    with open(GTFS_DIR / "stops.txt", encoding="utf-8") as f:
        reader: csv.DictReader[str] = csv.DictReader(f)
        for row in reader:
            if row["location_type"] == "0":
                stops[row["stop_id"]] = row["stop_name"]
    return stops


def load_stops_by_name() -> dict[StopName, list[StopId]]:
    """Zwraca mapę stop_name -> [stop_id, ...] (jeden przystanek może mieć wiele ID)."""
    result: dict[StopName, list[StopId]] = defaultdict(list)
    with open(GTFS_DIR / "stops.txt", encoding="utf-8") as f:
        reader: csv.DictReader[str] = csv.DictReader(f)
        for row in reader:
            if row["location_type"] == "0":
                result[row["stop_name"]].append(row["stop_id"])
    return dict(result)


def load_active_service_ids(travel_date: date) -> set[ServiceId]:
    """
    Zwraca zbiór service_id aktywnych w podanym dniu.
    Uwzględnia calendar.txt (wzorzec tygodniowy) i calendar_dates.txt (wyjątki).
    """
    day_column: str = [
        "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"
    ][travel_date.weekday()]

    date_int: int = int(travel_date.strftime("%Y%m%d"))
    active: set[ServiceId] = set()

    with open(GTFS_DIR / "calendar.txt", encoding="utf-8") as f:
        reader: csv.DictReader[str] = csv.DictReader(f)
        for row in reader:
            if (
                int(row["start_date"]) <= date_int <= int(row["end_date"])
                and row[day_column] == "1"
            ):
                active.add(row["service_id"])

    with open(GTFS_DIR / "calendar_dates.txt", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if int(row["date"]) == date_int:
                if row["exception_type"] == "1":
                    active.add(row["service_id"])
                elif row["exception_type"] == "2":
                    active.discard(row["service_id"])

    return active


def load_active_trip_ids(active_service_ids: set[ServiceId]) -> set[TripId]:
    """Zwraca zbiór trip_id dla aktywnych service_id."""
    active_trips: set[TripId] = set()
    with open(GTFS_DIR / "trips.txt", encoding="utf-8") as f:
        reader: csv.DictReader[str] = csv.DictReader(f)
        for row in reader:
            if row["service_id"] in active_service_ids:
                active_trips.add(row["trip_id"])
    return active_trips


def load_connections(active_trip_ids: set[TripId]) -> list[Connection]:
    """
    Buduje listę połączeń między kolejnymi przystankami dla aktywnych kursów.
    Każda krawędź = jeden odcinek kursu (przystanek N -> przystanek N+1).
    """
    trip_stops: dict[TripId, list[StopVisit]] = defaultdict(list)

    with open(GTFS_DIR / "stop_times.txt", encoding="utf-8") as f:
        reader: csv.DictReader[str] = csv.DictReader(f)
        for row in reader:
            trip_id: TripId = row["trip_id"]
            if trip_id not in active_trip_ids:
                continue
            trip_stops[trip_id].append(StopVisit(
                sequence=int(row["stop_sequence"]),
                stop_id=row["stop_id"],
                arrival_time=time_to_seconds(row["arrival_time"]),
                departure_time=time_to_seconds(row["departure_time"]),
            ))

    connections: list[Connection] = []
    for trip_id, visits in trip_stops.items():
        sorted_visits: list[StopVisit] = sorted(visits, key=lambda v: v.sequence)  # kolejność przystanków w kursie
        for i in range(len(sorted_visits) - 1):
            from_visit: StopVisit = sorted_visits[i]
            to_visit: StopVisit = sorted_visits[i + 1]
            connections.append(Connection(
                trip_id=trip_id,
                from_stop_id=from_visit.stop_id,
                to_stop_id=to_visit.stop_id,
                departure_time=from_visit.departure_time,
                arrival_time=to_visit.arrival_time,
            ))

    return connections


def load_stop_coords() -> dict[StopId, tuple[float, float]]:
    """Zwraca mapę stop_id -> (lat, lon)."""
    coords: dict[StopId, tuple[float, float]] = {}
    with open(GTFS_DIR / "stops.txt", encoding="utf-8") as f:
        reader: csv.DictReader[str] = csv.DictReader(f)
        for row in reader:
            if row["location_type"] == "0":
                coords[row["stop_id"]] = (float(row["stop_lat"]), float(row["stop_lon"]))
    return coords


def load_trip_to_route() -> dict[TripId, str]:
    """Zwraca mapę trip_id -> route_short_name."""
    route_names: dict[str, str] = {}
    with open(GTFS_DIR / "routes.txt", encoding="utf-8") as f:
        reader: csv.DictReader[str] = csv.DictReader(f)
        for row in reader:
            route_names[row["route_id"]] = row["route_short_name"]

    result: dict[TripId, str] = {}
    with open(GTFS_DIR / "trips.txt", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            result[row["trip_id"]] = route_names.get(row["route_id"], row["route_id"])
    return result


def build_graph(connections: list[Connection]) -> Graph:
    """Buduje graf sąsiedztwa: stop_id -> lista Connection wychodzących z tego przystanku."""
    graph: Graph = defaultdict(list)
    for conn in connections:
        graph[conn.from_stop_id].append(conn)
    return dict(graph)


def main() -> None:
    from datetime import date

    stops: dict[StopId, StopName] = load_stops()
    active_services: set[ServiceId] = load_active_service_ids(date.today())
    active_trips: set[TripId] = load_active_trip_ids(active_services)
    connections: list[Connection] = load_connections(active_trips)
    graph: Graph = build_graph(connections)

    print(f"Wierzchołki (przystanki): {len(graph)}")
    print(f"Krawędzie (połączenia):   {len(connections)}\n")

    from_stop_id: StopId
    edges: list[Connection]
    for from_stop_id, edges in sorted(graph.items(), key=lambda kv: stops.get(kv[0], kv[0])):
        from_name: StopName = stops.get(from_stop_id, from_stop_id)
        print(f"{from_name}:")
        conn: Connection
        for conn in sorted(edges, key=lambda c: c.departure_time):
            to_name: StopName = stops.get(conn.to_stop_id, conn.to_stop_id)
            print(f"  {seconds_to_time(conn.departure_time)} → {to_name} (przybycie {seconds_to_time(conn.arrival_time)})")


if __name__ == "__main__":
    main()
