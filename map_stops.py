"""
Generuje mapę HTML ze wszystkimi przystankami z pliku stops.txt.

Użycie:
    python3 map_stops.py [output.html]
"""
import csv
import sys

import folium

STOPS_FILE = "google_transit/stops.txt"
OUTPUT = sys.argv[1] if len(sys.argv) > 1 else "stops_map.html"


def load_stops() -> list[dict]:
    stops = []
    with open(STOPS_FILE, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["location_type"] == "0":
                stops.append({
                    "stop_id": row["stop_id"],
                    "name": row["stop_name"],
                    "lat": float(row["stop_lat"]),
                    "lon": float(row["stop_lon"]),
                })
    return stops


def main() -> None:
    stops = load_stops()
    print(f"Wczytano {len(stops)} przystanków.")

    lats = [s["lat"] for s in stops]
    lons = [s["lon"] for s in stops]
    center = (sum(lats) / len(lats), sum(lons) / len(lons))

    m = folium.Map(location=center, zoom_start=8, tiles="CartoDB positron")

    for s in stops:
        folium.CircleMarker(
            location=(s["lat"], s["lon"]),
            radius=4,
            color="#2563eb",
            fill=True,
            fill_color="#2563eb",
            fill_opacity=0.7,
            tooltip=f"{s['name']} (id: {s['stop_id']})",
        ).add_to(m)

    m.save(OUTPUT)
    print(f"Mapa zapisana: {OUTPUT}")


if __name__ == "__main__":
    main()
