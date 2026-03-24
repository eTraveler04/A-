"""
Generuje mapę HTML przystanków, z których można odjechać I do których można przyjechać.

Użycie:
    python map_active_stops.py [dzien] [output.html]
    python map_active_stops.py pon
    python map_active_stops.py pon active_stops.html
"""
import sys
import folium
from datetime import date, timedelta

from gtfs_loader import (
    load_stops,
    load_stop_coords,
    load_active_service_ids,
    load_active_trip_ids,
    load_connections,
    build_graph,
)
from utils import parse_day

day_str = sys.argv[1] if len(sys.argv) > 1 else "pon"
output = sys.argv[2] if len(sys.argv) > 2 else "active_stops.html"

travel_date = parse_day(day_str)

print(f"Wczytywanie danych dla: {travel_date} ({day_str})...")
services = load_active_service_ids(travel_date)
trips = load_active_trip_ids(services)
connections = load_connections(trips)

next_day_services = load_active_service_ids(travel_date + timedelta(days=1))
next_day_trips = load_active_trip_ids(next_day_services)
connections += load_connections(next_day_trips, time_offset=86400)

graph = build_graph(connections)

stops = load_stops()
coords = load_stop_coords()

# Przystanki z których można odjechać
can_depart = set(graph.keys())

# Przystanki do których można przyjechać
can_arrive = set(conn.to_stop_id for conns in graph.values() for conn in conns)

# Tylko te, które mają oba
active = can_depart & can_arrive

print(f"Przystanki aktywne (odjazd i przyjazd): {len(active)} / {len(stops)}")

known = [(coords[s][0], coords[s][1]) for s in active if s in coords]
center_lat = sum(lat for lat, _ in known) / len(known)
center_lon = sum(lon for _, lon in known) / len(known)

m = folium.Map(location=[center_lat, center_lon], zoom_start=8, tiles="CartoDB positron")

for sid in active:
    if sid not in coords:
        continue
    lat, lon = coords[sid]
    name = stops.get(sid, sid)
    folium.CircleMarker(
        location=(lat, lon),
        radius=4,
        color="#2563eb",
        fill=True,
        fill_color="#2563eb",
        fill_opacity=0.8,
        tooltip=name,
        popup=folium.Popup(f"<b>{name}</b><br>id: {sid}", max_width=200),
    ).add_to(m)

m.save(output)
print(f"Mapa zapisana: {output}")
