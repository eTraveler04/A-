"""
Wizualizacja trasy zwróconej przez dijkstrę na mapie Folium.
Użycie: wywoływane z main.py po znalezieniu trasy.
"""
import folium
from itertools import groupby

from models import Connection, PathResult, StopId, StopName
from gtfs_loader import seconds_to_time

# Kolory dla kolejnych linii na trasie
COLORS = ["red", "blue", "green", "purple", "orange", "darkred", "cadetblue"]


def visualize(
    result: PathResult,
    stops: dict[StopId, StopName],
    coords: dict[StopId, tuple[float, float]],
    route_names: dict[str, str],
    output_path: str = "trasa.html",
) -> None:
    # Środek mapy = średnia współrzędnych przystanków na trasie
    all_stop_ids = [result.legs[0].from_stop_id] + [leg.to_stop_id for leg in result.legs]
    known = [coords[s] for s in all_stop_ids if s in coords]
    center_lat = sum(lat for lat, _ in known) / len(known)
    center_lon = sum(lon for _, lon in known) / len(known)

    m = folium.Map(location=[center_lat, center_lon], zoom_start=10, tiles="OpenStreetMap")

    # Rysuj odcinki — jeden kolor per kurs (trip_id)
    color_idx = 0
    for trip_id, group in groupby(result.legs, key=lambda c: c.trip_id):
        segments: list[Connection] = list(group)
        route = route_names.get(trip_id, trip_id)
        color = COLORS[color_idx % len(COLORS)]
        color_idx += 1

        # Zbierz punkty dla tej linii
        points: list[tuple[float, float]] = []
        first = segments[0]
        if first.from_stop_id in coords:
            points.append(coords[first.from_stop_id])
        for seg in segments:
            if seg.to_stop_id in coords:
                points.append(coords[seg.to_stop_id])

        if len(points) >= 2:
            folium.PolyLine(
                points,
                color=color,
                weight=5,
                opacity=0.85,
                tooltip=f"Linia {route}",
            ).add_to(m)

    # Markery przystanków
    for i, leg in enumerate(result.legs):
        # Przystanek wsiadania (tylko przy pierwszym odcinku lub przesiadce)
        if i == 0 or leg.trip_id != result.legs[i - 1].trip_id:
            sid = leg.from_stop_id
            if sid in coords:
                name = stops.get(sid, sid)
                folium.CircleMarker(
                    location=coords[sid],
                    radius=7,
                    color="black",
                    fill=True,
                    fill_color="white",
                    fill_opacity=1.0,
                    popup=folium.Popup(
                        f"<b>{name}</b><br>odjazd: {seconds_to_time(leg.departure_time)}",
                        max_width=200,
                    ),
                    tooltip=name,
                ).add_to(m)

    # Przystanek końcowy
    last_leg = result.legs[-1]
    sid = last_leg.to_stop_id
    if sid in coords:
        name = stops.get(sid, sid)
        folium.Marker(
            location=coords[sid],
            popup=folium.Popup(
                f"<b>{name}</b><br>przyjazd: {seconds_to_time(last_leg.arrival_time)}",
                max_width=200,
            ),
            tooltip=name,
            icon=folium.Icon(color="green", icon="flag"),
        ).add_to(m)

    # Przystanek startowy
    first_leg = result.legs[0]
    sid = first_leg.from_stop_id
    if sid in coords:
        name = stops.get(sid, sid)
        folium.Marker(
            location=coords[sid],
            popup=folium.Popup(
                f"<b>{name}</b><br>odjazd: {seconds_to_time(first_leg.departure_time)}",
                max_width=200,
            ),
            tooltip=name,
            icon=folium.Icon(color="red", icon="home"),
        ).add_to(m)

    m.save(output_path)
    print(f"Mapa zapisana: {output_path}")
