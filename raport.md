# Raport — Zadanie 1: Wyszukiwanie najkrótszych ścieżek w sieci Kolei Dolnośląskich

**Przedmiot:** Sztuczna inteligencja i inżynieria wiedzy
**Dane:** GTFS Koleje Dolnośląskie, ważne 03.03.2026–12.12.2026

---

## 1. Tło teoretyczne

### 1.1 Problem wyszukiwania ścieżki w transporcie publicznym

Sieć połączeń kolejowych modelowana jest jako skierowany graf zależny od czasu. Każdy wierzchołek reprezentuje przystanek (stację), a każda krawędź — jeden odcinek kursu pociągu między dwoma kolejnymi przystankami. Krawędź posiada dwa znaczące atrybuty czasowe: czas odjazdu i czas przyjazdu. Pasażer może skorzystać z krawędzi tylko wtedy, gdy przybywa na przystanek **przed** czasem odjazdu danego kursu.

Formalnie, dla każdej pary kolejnych przystanków $(i, i+1)$ w kursie tworzona jest krawędź:

$$e = (\text{stop}_i \to \text{stop}_{i+1},\ \text{departure\_time}_i,\ \text{arrival\_time}_{i+1})$$

Przesiadka modelowana jest implicitnie — pasażer czeka na przystanku do najbliższego dostępnego odjazdu.

### 1.2 Algorytm Dijkstry

Algorytm Dijkstry znajduje najkrótszą ścieżkę w grafie ważonym z nieujemnymi wagami. Operuje na kolejce priorytetowej, z której zawsze wybierany jest wierzchołek o najniższym dotychczasowym koszcie $g(v)$.

Inicjalizacja:
$$g(s) = t_\text{start}, \quad g(v) = \infty \text{ dla } v \neq s$$

Relaksacja krawędzi — dla każdego sąsiada $u$ bieżącego wierzchołka $v$:
$$\text{jeśli } \text{departure}(v \to u) \geq g(v) \text{ oraz } \text{arrival}(v \to u) < g(u): \quad g(u) \leftarrow \text{arrival}(v \to u)$$

Algorytm kończy się, gdy cel zostaje wyciągnięty z kolejki — wtedy $g(\text{cel})$ jest minimalnym możliwym czasem przybycia.

### 1.3 Algorytm A*

A* jest rozszerzeniem Dijkstry o funkcję heurystyczną $h(v)$, która szacuje minimalny koszt dotarcia z wierzchołka $v$ do celu. Priorytet w kolejce wyznaczany jest przez:

$$f(v) = g(v) + h(v)$$

gdzie $g(v)$ to rzeczywisty koszt, a $h(v)$ to szacunek pozostałego kosztu.

**Warunek dopuszczalności heurystyki:** $h(v)$ nigdy nie może przeszacowywać rzeczywistego kosztu:
$$h(v) \leq h^*(v)$$

Gwarantuje to, że A* znajdzie rozwiązanie optymalne. Jeśli heurystyka jest trywialna ($h \equiv 0$), A* degeneruje się do Dijkstry.

Węzły w złym kierunku od celu otrzymują duże $h$, przez co trafiają na koniec kolejki i naturalnie nie są eksplorowane jeśli cel zostanie znaleziony wcześniej — stąd przyspieszenie względem Dijkstry.

### 1.4 A* z kryterium czasu

Koszt $g(v)$ wyrażony jest w sekundach (czas przybycia). Heurystyka szacuje minimalny czas dotarcia z przystanku $v$ do celu jako odległość euklidesową w linii prostej podzieloną przez maksymalną prędkość pociągu:

$$h(v) = \frac{d_\text{euklid}(v,\ \text{cel})}{v_\text{max}}$$

gdzie $v_\text{max} = 44{,}4\ \text{m/s} \approx 160\ \text{km/h}$.

Odległość euklidesowa liczona jest ze współrzędnych geograficznych WGS84 z przeliczeniem stopni na metry:

$$d = \sqrt{(\Delta\phi \cdot 111320)^2 + (\Delta\lambda \cdot 111320 \cdot \cos\bar{\phi})^2}$$

Ponieważ pociąg nigdy nie pokona tej odległości szybciej niż jadąc 160 km/h w linii prostej, heurystyka jest dopuszczalna.

### 1.5 A* z kryterium przesiadek

Koszt $g(v)$ jest krotką $(p, t)$, gdzie $p$ to liczba przesiadek, $t$ to czas przybycia. Sortowanie leksykograficzne — minimalizujemy przesiadki, przy remisie minimalizujemy czas.

Stan algorytmu rozszerzony jest o aktualny kurs: $v = (\text{stop\_id},\ \text{trip\_id})$. Przesiadka naliczana jest gdy pasażer zmienia `trip_id`.

Heurystyka opiera się na pytaniu: czy obecny kurs dojedzie do celu bez żadnej przesiadki?

$$h(v) = \begin{cases} 0 & \text{jeśli } \text{trip\_id}(v) \in \text{trips\_to\_target} \\ 1 & \text{w przeciwnym razie} \end{cases}$$

gdzie $\text{trips\_to\_target}$ to zbiór kursów, które zatrzymują się na stacji docelowej. Jest to heurystyka dopuszczalna — jeśli obecny kurs nie dociera do celu, co najmniej jedna przesiadka jest nieunikniona.

Funkcja priorytetu w kolejce:

$$f = (g_p + h,\ g_t)$$

Heurystyka dodawana jest wyłącznie do składowej przesiadkowej krotki, nie do czasu.

---

## 2. Implementacja

### 2.1 Przygotowanie danych GTFS

Dane wejściowe to pliki GTFS Kolei Dolnośląskich. Przed uruchomieniem algorytmu należy:

1. Ustalić, które kursy są aktywne w podanym dniu (filtrowanie przez `calendar.txt` i `calendar_dates.txt`)
2. Zbudować graf połączeń na podstawie `stop_times.txt`

**Fragment 1 — filtrowanie aktywnych kursów (`gtfs_loader.py:83`)**

```python
def load_active_service_ids(travel_date: date) -> set[ServiceId]:
    day_column = ["monday", ..., "sunday"][travel_date.weekday()]
    date_int = int(travel_date.strftime("%Y%m%d"))
    active: set[ServiceId] = set()

    # Krok 1: wzorzec tygodniowy z calendar.txt
    with open(GTFS_DIR / "calendar.txt") as f:
        for row in csv.DictReader(f):
            if (int(row["start_date"]) <= date_int <= int(row["end_date"])
                    and row[day_column] == "1"):
                active.add(row["service_id"])

    # Krok 2: nadpisanie wyjątkami z calendar_dates.txt (np. święta)
    with open(GTFS_DIR / "calendar_dates.txt") as f:
        for row in csv.DictReader(f):
            if int(row["date"]) == date_int:
                if row["exception_type"] == "1":
                    active.add(row["service_id"])     # kurs dodany wyjątkowo
                elif row["exception_type"] == "2":
                    active.discard(row["service_id"]) # kurs odwołany wyjątkowo

    return active
```

Funkcja najpierw zbiera kursy pasujące do dnia tygodnia w przedziale dat, a następnie koryguje wynik o wyjątki (np. dodatkowe kursy świąteczne lub zawieszone połączenia). Dzięki temu algorytm operuje wyłącznie na kursach faktycznie kursujących w podanym dniu.

---

**Fragment 2 — budowanie grafu połączeń (`gtfs_loader.py:127`)**

```python
def load_connections(active_trip_ids: set[TripId], time_offset: Seconds = 0) -> list[Connection]:
    norm = load_stop_normalization()  # mapuje peron -> stacja nadrzędna
    trip_stops: dict[TripId, list[StopVisit]] = defaultdict(list)

    # Wczytanie wszystkich zatrzymań aktywnych kursów
    with open(GTFS_DIR / "stop_times.txt") as f:
        for row in csv.DictReader(f):
            if row["trip_id"] not in active_trip_ids:
                continue
            trip_stops[row["trip_id"]].append(StopVisit(
                sequence=int(row["stop_sequence"]),
                stop_id=norm.get(row["stop_id"], row["stop_id"]),  # normalizacja do stacji
                arrival_time=time_to_seconds(row["arrival_time"]) + time_offset,
                departure_time=time_to_seconds(row["departure_time"]) + time_offset,
                ...
            ))

    connections = []
    for trip_id, visits in trip_stops.items():
        sorted_visits = sorted(visits, key=lambda v: v.sequence)
        for i in range(len(sorted_visits) - 1):
            from_v, to_v = sorted_visits[i], sorted_visits[i + 1]
            # Pomijamy przystanki bez wsiadania lub wysiadania
            if from_v.pickup_type == 1 or to_v.drop_off_type == 1:
                continue
            connections.append(Connection(
                trip_id=trip_id,
                from_stop_id=from_v.stop_id,
                to_stop_id=to_v.stop_id,
                departure_time=from_v.departure_time,
                arrival_time=to_v.arrival_time,
            ))
    return connections
```

Dla każdego kursu przystanki sortowane są po `stop_sequence`, a następnie tworzone są krawędzie między każdą parą kolejnych przystanków. `time_offset=86400` używany jest do wczytania kursów następnego dnia — dzięki temu podróże przekraczające północ obsługiwane są poprawnie.

---

### 2.2 Konfiguracja wyszukiwania — wzorzec SearchConfig

Zamiast implementować osobno Dijkstrę i A*, zastosowano wzorzec konfiguracji — `SearchConfig` definiuje kryterium optymalizacji jako zestaw funkcji. Właściwy algorytm (`search`) jest wspólny dla obu wariantów.

**Fragment 3 — Dijkstra z kryterium czasu (`dijkstra.py:59`)**

```python
def make_time_config() -> SearchConfig:
    return SearchConfig(
        # Stan początkowy: każda stacja źródłowa z kosztem = czas odjazdu
        initial_states=lambda source_ids, t: [(t, sid) for sid in source_ids],

        # Ekspansja: kursy odjeżdżające nie wcześniej niż bieżący czas przybycia
        expand=lambda state, cost, graph: [
            (conn.arrival_time, conn.to_stop_id, conn)
            for conn in graph.get(state, [])
            if conn.departure_time >= cost   # warunek zdążenia na pociąg
        ],

        is_goal=lambda state, target_ids: state in target_ids,
        get_stop_id=lambda state: state,
        get_arrival_time=lambda cost: cost,
    )
```

Stan to `stop_id`, koszt to czas przybycia w sekundach. Warunek `departure_time >= cost` gwarantuje, że pasażer nie wsiada do pociągu który już odjechał.

---

**Fragment 4 — A* z kryterium czasu (`dijkstra.py:101`)**

```python
def make_astar_time_config(
    coords: dict[StopId, tuple[float, float]],
    target_ids: set[StopId],
    max_speed_ms: float = 44.4,   # 160 km/h — górna granica prędkości KD
) -> SearchConfig:
    target_coords = [coords[sid] for sid in target_ids if sid in coords]

    def heuristic(state: StopId, _target_ids: set[StopId]) -> Seconds:
        if state not in coords or not target_coords:
            return 0  # brak danych → heurystyka trywialna (bezpieczne)
        lat1, lon1 = coords[state]
        # Minimalna odległość do któregokolwiek z przystanków docelowych
        min_dist = min(
            math.sqrt(
                ((lat2 - lat1) * 111_320) ** 2
                + ((lon2 - lon1) * 111_320 * math.cos(math.radians((lat1 + lat2) / 2))) ** 2
            )
            for lat2, lon2 in target_coords
        )
        return int(min_dist / max_speed_ms)  # sekundy

    config = make_time_config()   # A* = Dijkstra + heurystyka
    config.heuristic = heuristic
    return config
```

Heurystyka zwraca minimalny szacowany czas (w sekundach) do celu — odległość euklidesową w metrach podzieloną przez maksymalną prędkość. Prędkość 160 km/h jest górną granicą, więc $h(v) \leq h^*(v)$ — heurystyka jest dopuszczalna.

---

**Fragment 5 — A* z kryterium przesiadek (`dijkstra.py:101`)**

```python
def make_astar_transfers_config(graph: Graph, target_ids: set[StopId]) -> SearchConfig:
    # Prekomputacja: które kursy docierają do stacji docelowej?
    trips_to_target: set[str] = set()
    for connections in graph.values():
        for conn in connections:
            if conn.to_stop_id in target_ids:
                trips_to_target.add(conn.trip_id)

    def heuristic(state: tuple, _target_ids: set[StopId]) -> int:
        stop_id, trip_id = state
        if stop_id in target_ids:
            return 0  # już na miejscu
        if trip_id is not None and trip_id in trips_to_target:
            return 0  # ten kurs dojedzie do celu — 0 przesiadek więcej
        return 1      # konieczna co najmniej 1 przesiadka

    config = make_transfers_config()
    config.heuristic = heuristic
    # h dodajemy tylko do składowej przesiadkowej, nie do czasu
    config.make_f = lambda cost, h: (cost[0] + h, cost[1])
    return config
```

Prekomputacja `trips_to_target` wykonywana jest raz przed startem algorytmu w czasie $O(|E|)$. Każde wywołanie heurystyki to sprawdzenie przynależności do zbioru — $O(1)$.

---

**Fragment 6 — wspólny algorytm wyszukiwania (`dijkstra.py:132`)**

```python
def search(graph, source_ids, target_ids, departure_time, config):
    h = config.heuristic   # None → Dijkstra, funkcja → A*

    best_cost: dict[State, Cost] = {}
    prev: dict[State, tuple[State, Connection] | None] = {}
    queue = []

    for cost, state in config.initial_states(source_ids, departure_time):
        best_cost[state] = cost
        prev[state] = None
        if h:
            h_val = h(state, target_ids)
            # make_f definiuje jak łączyć g z h (różne dla int i krotki)
            f = config.make_f(cost, h_val) if config.make_f else cost + h_val
        else:
            f = cost
        heapq.heappush(queue, (f, next(counter), cost, state))

    while queue:
        _, _, current_cost, current_state = heapq.heappop(queue)

        # Wpis zdezaktualizowany — znaleziono już lepszą ścieżkę do tego stanu
        if current_cost != best_cost.get(current_state):
            continue

        # Cel wyciągnięty z kolejki → optymalna ścieżka znaleziona
        if config.is_goal(current_state, target_ids):
            return _build_result(...)

        for new_cost, new_state, conn in config.expand(current_state, current_cost, graph):
            if new_state not in best_cost or new_cost < best_cost[new_state]:
                best_cost[new_state] = new_cost
                prev[new_state] = (current_state, conn)
                if h:
                    h_val = h(new_state, target_ids)
                    new_f = config.make_f(new_cost, h_val) if config.make_f else new_cost + h_val
                else:
                    new_f = new_cost
                heapq.heappush(queue, (new_f, next(counter), new_cost, new_state))

    return None  # brak połączenia
```

Algorytm jest wspólny dla wszystkich wariantów — Dijkstra, A* czasu i A* przesiadek. Różnią się wyłącznie konfiguracją: definicją kosztu, funkcją ekspansji i heurystyką. Gdy `heuristic = None`, algorytm degeneruje się do Dijkstry. Pole `make_f` obsługuje przypadek gdy koszt jest krotką — heurystyka dodawana jest tylko do wybranej składowej.

---

## 3. Przykładowe wyniki

Testy wykonano na danych rozkładowych Kolei Dolnośląskich, poniedziałek.

### Przykład 1 — Wrocław Główny → Jelenia Góra, odjazd 10:00

| | Dijkstra czas (`t`) | A* czas (`at`) | A* przesiadki (`ap`) |
|---|---|---|---|
| Trasa | Wrocław Gł. → Jelenia Góra [D6] | j.w. | j.w. |
| Odjazd | 10:10 | 10:10 | 10:10 |
| Przyjazd | 12:26 | 12:26 | 12:26 |
| Przesiadki | 0 | 0 | 0 |
| Odwiedzone węzły | **207** | **145** | **44** |
| Czas obliczenia | 0.002s | 0.002s | 0.003s |

Trasa bezpośrednia — wszystkie algorytmy zwracają ten sam wynik. A* przesiadki odwiedza zaledwie 44 węzły, bo heurystyka natychmiast rozpoznaje że kurs D6 dociera do celu i nadaje mu priorytet 0.

---

### Przykład 2 — Wrocław Główny → Legnica, odjazd 08:30

| | Dijkstra czas (`t`) | A* czas (`at`) | A* przesiadki (`ap`) |
|---|---|---|---|
| Trasa | D2: Wrocław → Wrocław Muchobór, D1: Wrocław Muchobór → Legnica | j.w. | D1: Wrocław Gł. → Legnica |
| Odjazd | 08:43 | 08:43 | 08:49 |
| Przyjazd | 09:45 | 09:45 | 09:45 |
| Przesiadki | 1 | 1 | **0** |
| Odwiedzone węzły | **70** | **43** | **20** |
| Czas obliczenia | 0.001s | 0.001s | 0.002s |

A* przesiadki znalazł trasę bezpośrednią D1 (odjazd 08:49), którą kryterium czasu pominęło na rzecz wcześniejszego połączenia z przesiadką (08:43). Wynik różny — różne kryteria optymalizacji.

---

### Przykład 3 — Wrocław Główny → Karpacz, odjazd 15:20

| | Dijkstra czas (`t`) | A* czas (`at`) | A* przesiadki (`ap`) |
|---|---|---|---|
| Leg 1 | D6: Wrocław → Wałbrzych 15:40→16:46 | j.w. | D6: Wrocław → Jelenia Góra 15:55→18:10 |
| Leg 2 | D6: Wałbrzych → Jelenia Góra 17:01→18:10 | j.w. | D62: Jelenia Góra → Karpacz 18:35→18:53 |
| Leg 3 | D62: Jelenia Góra → Karpacz 18:35→18:53 | j.w. | — |
| Przyjazd | 18:53 | 18:53 | 18:53 |
| Przesiadki | 2 | 2 | **1** |
| Odwiedzone węzły | **267** | **250** | **928** |
| Czas obliczenia | 0.003s | 0.003s | 0.034s |

A* przesiadki znalazł trasę o jedną przesiadkę krótszą — poczekał na D6 o 15:55, który jedzie bezpośrednio do Jeleniej Góry bez zmiany kursu. Kryterium czasu wybrało wcześniejszy pociąg (15:40), który jednak wymaga zmiany składu w Wałbrzychu. A* przesiadki odwiedził więcej węzłów niż warianty czasowe — heurystyka binarna (0/1) jest mniej precyzyjna niż heurystyka geograficzna.

---

### Obserwacje

We wszystkich przypadkach wyniki są optymalne względem danego kryterium. Kryterium czasu i kryterium przesiadek mogą dawać różne trasy — jest to oczekiwane zachowanie. A* przesiadki odwiedza znacząco mniej węzłów niż Dijkstra przesiadki (np. Karpacz: 928 vs ~6000), jednak więcej niż A* czasu ze względu na mniej precyzyjną heurystykę binarną.

---

## 4. Użyte biblioteki

| Biblioteka | Zastosowanie |
|---|---|
| `heapq` (stdlib) | Kolejka priorytetowa w Dijkstrze i A* |
| `csv` (stdlib) | Parsowanie plików GTFS (.txt) |
| `datetime` (stdlib) | Obliczanie dnia tygodnia, filtrowanie kalendarza |
| `math` (stdlib) | Obliczanie odległości euklidesowej dla heurystyki |
| `collections.defaultdict` (stdlib) | Budowanie grafu sąsiedztwa |
| `folium` | Generowanie interaktywnej mapy HTML z wynikiem trasy |

Implementacja nie wymaga żadnych zewnętrznych zależności poza `folium` (wizualizacja).
