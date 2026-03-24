# Raport — Zadanie 1: Wyszukiwanie najkrótszych ścieżek w sieci Kolei Dolnośląskich

**Przedmiot:** Sztuczna inteligencja i inżynieria wiedzy
**Dane:** GTFS Koleje Dolnośląskie, ważne 03.03.2026–12.12.2026

---

## 1. Tło teoretyczne

### 1.1 Problem wyszukiwania ścieżki w transporcie publicznym

Sieć połączeń kolejowych modelowana jest jako **skierowany graf zależny od czasu**. Każdy wierzchołek reprezentuje przystanek (stację), a każda krawędź — jeden odcinek kursu pociągu między dwoma kolejnymi przystankami. Krawędź posiada dwa atrybuty czasowe: czas odjazdu i czas przyjazdu. Pasażer może skorzystać z krawędzi tylko wtedy, gdy przybywa na przystanek **nie później** niż czas odjazdu danego kursu.

Formalnie, dla każdej pary kolejnych przystanków $(i, i+1)$ w kursie tworzona jest krawędź:

$$e = (\text{stop}_i \to \text{stop}_{i+1},\ \text{departure\_time}_i,\ \text{arrival\_time}_{i+1})$$

Przesiadka modelowana jest implicitnie — pasażer czeka na przystanku do najbliższego dostępnego odjazdu w kierunku celu.

Graf jest zależny od czasu — w przeciwieństwie do klasycznego grafu ważonego, koszt przejścia krawędzią zależy nie tylko od jej wagi, ale też od momentu przybycia do wierzchołka. Pasażer, który przyjedzie za późno, musi poczekać na następny kurs.

### 1.2 Algorytm Dijkstry

Algorytm Dijkstry znajduje najkrótszą ścieżkę w grafie ważonym z nieujemnymi wagami. Operuje na kolejce priorytetowej, z której zawsze wybierany jest wierzchołek o najniższym dotychczasowym koszcie $g(v)$.

**Inicjalizacja:**
$$g(s) = t_\text{start}, \quad g(v) = \infty \text{ dla } v \neq s$$

**Relaksacja krawędzi** — dla każdego sąsiada $u$ bieżącego wierzchołka $v$:
$$\text{jeśli } \text{departure}(v \to u) \geq g(v) \text{ oraz } \text{arrival}(v \to u) < g(u): \quad g(u) \leftarrow \text{arrival}(v \to u)$$

Warunek $\text{departure}(v \to u) \geq g(v)$ zapewnia, że pasażer zdąży na dany kurs. Algorytm kończy się gdy cel zostaje wyciągnięty z kolejki — w tym momencie $g(\text{cel})$ jest minimalnym możliwym czasem przybycia.

### 1.3 Algorytm A*

A* jest rozszerzeniem Dijkstry o funkcję heurystyczną $h(v)$, która szacuje minimalny koszt dotarcia z wierzchołka $v$ do celu. Priorytet w kolejce wyznaczany jest przez:

$$f(v) = g(v) + h(v)$$

gdzie $g(v)$ to rzeczywisty koszt dotychczasowej ścieżki, a $h(v)$ to szacunek pozostałego kosztu.

**Warunek dopuszczalności heurystyki:**
$$h(v) \leq h^*(v)$$

gdzie $h^*(v)$ to rzeczywisty minimalny koszt dotarcia z $v$ do celu. Gwarantuje to, że A* znajdzie rozwiązanie optymalne.

Węzły w złym kierunku od celu otrzymują duże $h$, przez co trafiają na koniec kolejki i naturalnie nie są eksplorowane jeśli cel zostanie znaleziony wcześniej — stąd przyspieszenie względem Dijkstry. Gdy $h \equiv 0$, A* degeneruje się do Dijkstry.

### 1.4 A* z kryterium czasu — heurystyka euklidesowa (`at`)

Koszt $g(v)$ to czas przybycia w sekundach. Heurystyka szacuje minimalny czas dotarcia z przystanku $v$ do celu jako odległość euklidesową w linii prostej podzieloną przez maksymalną prędkość pociągu:

$$h(v) = \frac{d_\text{euklid}(v,\ \text{cel})}{v_\text{max}}, \quad v_\text{max} = 44{,}4\ \text{m/s} \approx 160\ \text{km/h}$$

Odległość euklidesowa liczona jest ze współrzędnych geograficznych WGS84 z przeliczeniem stopni na metry:

$$d = \sqrt{(\Delta\phi \cdot 111320)^2 + (\Delta\lambda \cdot 111320 \cdot \cos\bar{\phi})^2}$$

Heurystyka jest dopuszczalna, ponieważ pociąg nigdy nie pokona odległości między dwoma punktami szybciej niż jadąc 160 km/h w linii prostej.

### 1.5 A* z kryterium czasu — heurystyka oparta na odwróconej Dijkstrze (`ats`)

Heurystyka euklidesowa jest dopuszczalna, ale zgrubna — pociąg nigdy nie jedzie w linii prostej. Lepsza heurystyka powinna uwzględniać rzeczywistą topologię sieci.

**Odwrócona Dijkstra od celu** — przed startem algorytmu uruchamiamy Dijkstrę wstecz od stacji docelowej na uproszczonym grafie, gdzie waga krawędzi to minimalny czas przejazdu między przystankami (ignorujemy rozkład jazdy i czasy oczekiwania):

$$w_\text{min}(u \to v) = \min_{\text{kursy}} (\text{arrival}_v - \text{departure}_u)$$

Wynik $\text{dist}[v]$ stanowi dolne ograniczenie rzeczywistego czasu dotarcia z $v$ do celu. Heurystyka jest dopuszczalna, ponieważ:
- ignoruje czasy oczekiwania na przesiadki (zawsze $\geq 0$)
- używa minimalnych czasów przejazdu (rzeczywiste czasy są $\geq$ minimum)

Prekomputacja wykonywana jest raz w $O(|E| \log |V|)$ przed startem wyszukiwania.

### 1.6 A* z kryterium przesiadek (`ap`)

Koszt $g(v)$ jest krotką $(p, t)$, gdzie $p$ to liczba przesiadek, $t$ to czas przybycia. Sortowanie leksykograficzne — najpierw minimalizujemy przesiadki, przy remisie minimalizujemy czas.

Stan algorytmu rozszerzony jest o aktualny kurs: $v = (\text{stop\_id},\ \text{trip\_id})$. Przesiadka naliczana jest gdy pasażer zmienia `trip_id`.

Heurystyka opiera się na pytaniu: czy obecny kurs dojedzie do celu bez żadnej przesiadki?

$$h(v) = \begin{cases} 0 & \text{jeśli } \text{trip\_id}(v) \in \text{trips\_to\_target} \\ 1 & \text{w przeciwnym razie} \end{cases}$$

Jest to heurystyka dopuszczalna — jeśli obecny kurs nie dociera do celu, co najmniej jedna przesiadka jest nieunikniona.

Funkcja priorytetu w kolejce:
$$f = (g_p + h,\ g_t)$$

Heurystyka dodawana jest wyłącznie do składowej przesiadkowej krotki, nie do czasu.

---

## 2. Implementacja

### 2.1 Przygotowanie danych GTFS

Dane wejściowe to pliki GTFS Kolei Dolnośląskich. Przed uruchomieniem algorytmu należy ustalić, które kursy są aktywne w podanym dniu, a następnie zbudować graf połączeń.

**Fragment 1 — filtrowanie aktywnych kursów (`gtfs_loader.py`)**

```python
def load_active_service_ids(travel_date: date) -> set[ServiceId]:
    day_column = ["monday", ..., "sunday"][travel_date.weekday()]  # (1)
    date_int = int(travel_date.strftime("%Y%m%d"))                 # (2)
    active: set[ServiceId] = set()

    with open(GTFS_DIR / "calendar.txt") as f:
        for row in csv.DictReader(f):
            if (int(row["start_date"]) <= date_int <= int(row["end_date"])  # (3)
                    and row[day_column] == "1"):                             # (4)
                active.add(row["service_id"])

    with open(GTFS_DIR / "calendar_dates.txt") as f:
        for row in csv.DictReader(f):
            if int(row["date"]) == date_int:
                if row["exception_type"] == "1":
                    active.add(row["service_id"])      # (5)
                elif row["exception_type"] == "2":
                    active.discard(row["service_id"])  # (6)

    return active
```

- **(1)** Wyznacza kolumnę dnia tygodnia w `calendar.txt` (np. `"monday"`) na podstawie obiektu `date`.
- **(2)** Konwertuje datę do formatu `YYYYMMDD` (integer) — format używany w GTFS.
- **(3)** Sprawdza czy data podróży mieści się w przedziale ważności wzorca kursowania.
- **(4)** Sprawdza czy wzorzec jest aktywny w danym dniu tygodnia.
- **(5)** `exception_type=1` — kurs dodany wyjątkowo w tej dacie (np. dodatkowy kurs świąteczny).
- **(6)** `exception_type=2` — kurs odwołany w tej dacie (np. zawieszenie z powodu remontu).

Wyjątki z `calendar_dates.txt` **nadpisują** wzorzec tygodniowy — wywołanie `discard` usuwa service_id który był wcześniej dodany przez wzorzec.

---

**Fragment 2 — budowanie grafu połączeń (`gtfs_loader.py`)**

```python
def load_connections(active_trip_ids: set[TripId], time_offset: Seconds = 0) -> list[Connection]:
    norm = load_stop_normalization()              # (1)
    trip_stops: dict[TripId, list[StopTimeRow]] = defaultdict(list)

    with open(GTFS_DIR / "stop_times.txt") as f:
        for row in csv.DictReader(f):
            if row["trip_id"] not in active_trip_ids:  # (2)
                continue
            trip_stops[row["trip_id"]].append(StopTimeRow(
                sequence=int(row["stop_sequence"]),
                stop_id=norm.get(row["stop_id"], row["stop_id"]),  # (3)
                arrival_time=time_to_seconds(row["arrival_time"]) + time_offset,   # (4)
                departure_time=time_to_seconds(row["departure_time"]) + time_offset,
                pickup_type=int(row.get("pickup_type") or 0),
            ))

    connections = []
    for trip_id, stop_times in trip_stops.items():
        sorted_stop_times = sorted(stop_times, key=lambda v: v.sequence)   # (5)
        for i in range(len(sorted_stop_times) - 1):
            from_v, to_v = sorted_stop_times[i], sorted_stop_times[i + 1]
            if from_v.pickup_type == 1:                                     # (6)
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

- **(1)** Normalizacja peronów do stacji nadrzędnej — peron `2246926` (np. "Wrocław Gł. peron 1") mapowany jest do `parent_station`. Dzięki temu przesiadki między peronami tej samej stacji działają poprawnie.
- **(2)** Wczytujemy tylko kursy aktywne w podanym dniu — pomijamy resztę pliku.
- **(3)** `norm.get(stop_id, stop_id)` — jeśli przystanek ma stację nadrzędną, używamy jej ID; w przeciwnym razie zostawiamy oryginalne ID.
- **(4)** `time_offset=86400` używany jest przy wczytywaniu kursów następnego dnia — czas przesuwa się o 24h, dzięki czemu podróże przekraczające północ obsługiwane są poprawnie (np. kurs o 23:50 z przyjazdem o 00:30 następnego dnia).
- **(5)** Przystanki kursu sortowane po `stop_sequence` — gwarantuje poprawną kolejność nawet jeśli wiersze w pliku są nieuporządkowane.
- **(6)** `pickup_type=1` oznacza brak możliwości wsiadania — pomijamy takie krawędzie. Wysiadanie jest zawsze możliwe, więc `drop_off_type` nie jest sprawdzany.

---

### 2.2 Wzorzec SearchConfig — wspólny algorytm dla wszystkich kryteriów

Zamiast implementować osobno Dijkstrę i A*, zastosowano wzorzec konfiguracji. `SearchConfig` definiuje kryterium optymalizacji jako zestaw funkcji, a właściwy algorytm (`search`) jest wspólny dla wszystkich wariantów.

```python
@dataclass
class SearchConfig:
    initial_states: Callable[[set[StopId], Seconds], list[tuple[Cost, State]]]  # (1)
    expand:         Callable[[State, Cost, Graph], list[tuple[Cost, State, Connection]]]  # (2)
    is_goal:        Callable[[State, set[StopId]], bool]   # (3)
    get_stop_id:    Callable[[State], StopId]              # (4)
    get_arrival_time: Callable[[Cost], Seconds]            # (5)
    heuristic: Callable[[State, set[StopId]], Any] | None = None  # (6)
    make_f:    Callable[[Cost, Any], Any] | None = None           # (7)
    on_visit:  Callable[[int, State, Cost], None] | None = None   # (8)
```

- **(1)** `initial_states` — generuje stany startowe z kosztem początkowym. Dla kryterium czasu: `(czas_odjazdu, stop_id)`. Dla przesiadek: `((0, czas_odjazdu), (stop_id, None))`.
- **(2)** `expand` — generuje sąsiadów stanu. Zawiera logikę filtrowania krawędzi (np. warunek zdążenia na pociąg).
- **(3)** `is_goal` — sprawdza czy osiągnięto cel. Dla czasu: `state in target_ids`. Dla przesiadek: `state[0] in target_ids` (bo stan to krotka).
- **(4)** `get_stop_id` — wyłuskuje `stop_id` ze stanu (różne dla różnych typów stanu).
- **(5)** `get_arrival_time` — wyłuskuje czas przybycia z kosztu (różne dla `int` i krotki).
- **(6)** `heuristic` — funkcja $h(v)$. Gdy `None`, algorytm działa jak Dijkstra.
- **(7)** `make_f` — definiuje jak łączyć $g$ z $h$ przy obliczaniu priorytetu. Potrzebne gdy koszt jest krotką — nie można po prostu dodać `(p, t) + 1`.
- **(8)** `on_visit` — opcjonalny callback diagnostyczny wywoływany przy każdej wizycie węzła.

---

**Fragment 3 — Dijkstra z kryterium czasu (`t`)**

```python
def make_time_config() -> SearchConfig:
    return SearchConfig(
        initial_states=lambda source_ids, t: [(t, sid) for sid in source_ids],  # (1)
        expand=lambda state, cost, graph: [
            (conn.arrival_time, conn.to_stop_id, conn)
            for conn in graph.get(state, [])
            if conn.departure_time >= cost    # (2)
        ],
        is_goal=lambda state, target_ids: state in target_ids,
        get_stop_id=lambda state: state,
        get_arrival_time=lambda cost: cost,
    )
```

- **(1)** Każda stacja źródłowa startuje z kosztem równym najwcześniejszemu czasowi odjazdu. Możliwe jest wiele stacji źródłowych (różne perony tej samej stacji).
- **(2)** Kurs jest dostępny tylko jeśli odjeżdża nie wcześniej niż czas przybycia pasażera. Warunek ten modeluje oczekiwanie na przystanku.

---

**Fragment 4 — Dijkstra z kryterium przesiadek (`p`)**

```python
def make_transfers_config() -> SearchConfig:
    def expand(state: tuple, cost: tuple, graph: Graph) -> list:
        stop_id, current_trip = state          # (1)
        num_transfers, current_time = cost     # (2)
        result = []
        for conn in graph.get(stop_id, []):
            if conn.departure_time < current_time:
                continue
            is_transfer = current_trip is not None and conn.trip_id != current_trip  # (3)
            new_cost = (num_transfers + (1 if is_transfer else 0), conn.arrival_time)  # (4)
            result.append((new_cost, (conn.to_stop_id, conn.trip_id), conn))
        return result

    return SearchConfig(
        initial_states=lambda source_ids, t: [((0, t), (sid, None)) for sid in source_ids],  # (5)
        expand=expand,
        is_goal=lambda state, target_ids: state[0] in target_ids,
        get_stop_id=lambda state: state[0],
        get_arrival_time=lambda cost: cost[1],
    )
```

- **(1)** Stan rozszerzony o `trip_id` — wiemy którym pociągiem aktualnie jedziemy.
- **(2)** Koszt to krotka `(liczba_przesiadek, czas_przybycia)` — sortowanie leksykograficzne minimalizuje najpierw przesiadki.
- **(3)** Przesiadka naliczana jest gdy zmieniamy `trip_id`. Warunek `current_trip is not None` obsługuje stan startowy (jeszcze nie wsiedliśmy do żadnego pociągu).
- **(4)** Nowy koszt: jeśli przesiadka — `num_transfers + 1`, w przeciwnym razie bez zmiany.
- **(5)** Stan startowy: `trip_id = None` — nie jesteśmy jeszcze w żadnym pociągu.

---

**Fragment 5 — A* z kryterium czasu, heurystyka euklidesowa (`at`)**

```python
def make_astar_time_config(coords, target_ids, max_speed_ms=44.4) -> SearchConfig:
    target_coords = [coords[sid] for sid in target_ids if sid in coords]  # (1)

    def heuristic(state: StopId, _target_ids) -> Seconds:
        if state not in coords or not target_coords:
            return 0                                   # (2)
        lat1, lon1 = coords[state]
        min_dist = min(
            math.sqrt(
                ((lat2 - lat1) * 111_320) ** 2
                + ((lon2 - lon1) * 111_320 * math.cos(math.radians((lat1 + lat2) / 2))) ** 2
            )
            for lat2, lon2 in target_coords            # (3)
        )
        return int(min_dist / max_speed_ms)            # (4)

    config = make_time_config()
    config.heuristic = heuristic
    return config
```

- **(1)** Prekomputacja współrzędnych stacji docelowych — unikamy wielokrotnego wyszukiwania podczas wyszukiwania.
- **(2)** Gdy brak danych geograficznych, heurystyka zwraca 0 — A* degeneruje się do Dijkstry dla tego węzła, co jest bezpieczne.
- **(3)** Dla zestawu stacji docelowych (różne perony) bierzemy minimalną odległość.
- **(4)** Dzielimy przez prędkość wyrażoną w m/s — wynik w sekundach. `int()` zaokrągla w dół, co gwarantuje niedoszacowanie.

---

**Fragment 6 — A* z kryterium czasu, heurystyka oparta na odwróconej Dijkstrze (`ats`)**

```python
def make_astar_time_improved_config(graph: Graph, target_ids: set[StopId]) -> SearchConfig:
    # Krok 1: minimalne czasy przejazdu między przystankami
    min_travel: dict[tuple[StopId, StopId], int] = {}
    for conns in graph.values():
        for conn in conns:
            key = (conn.from_stop_id, conn.to_stop_id)
            t = conn.arrival_time - conn.departure_time       # (1)
            if key not in min_travel or t < min_travel[key]:
                min_travel[key] = t

    # Krok 2: odwrócony graf
    rev: dict[StopId, list[tuple[StopId, int]]] = defaultdict(list)
    for (from_stop, to_stop), t in min_travel.items():
        rev[to_stop].append((from_stop, t))                   # (2)

    # Krok 3: Dijkstra wstecz od celu
    dist: dict[StopId, int] = {}
    queue = []
    for tid in target_ids:
        dist[tid] = 0
        heapq.heappush(queue, (0, tid))                       # (3)

    while queue:
        d, v = heapq.heappop(queue)
        if d > dist.get(v, float("inf")):
            continue
        for u, t in rev.get(v, []):
            nd = d + t
            if nd < dist.get(u, float("inf")):
                dist[u] = nd
                heapq.heappush(queue, (nd, u))                # (4)

    def heuristic(state: StopId, _target_ids) -> Seconds:
        return dist.get(state, 0)                             # (5)

    config = make_time_config()
    config.heuristic = heuristic
    return config
```

- **(1)** Czas przejazdu na odcinku = `arrival - departure`. Bierzemy minimum ze wszystkich kursów obsługujących daną parę przystanków — dolne ograniczenie.
- **(2)** Odwrócenie krawędzi: zamiast `A → B`, tworzymy `B → A`. Pozwala na Dijkstrę "wstecz" od celu.
- **(3)** Inicjalizacja kolejki od wszystkich stacji docelowych z kosztem 0 — wieloźródłowa Dijkstra.
- **(4)** Standardowa relaksacja Dijkstry na odwróconym grafie. Wynik `dist[v]` to minimalna suma czasów przejazdu z $v$ do celu, ignorując oczekiwanie.
- **(5)** Heurystyka to prekomputowana dolna granica. Dla przystanków poza siecią KD zwraca 0 (bezpieczne).

---

**Fragment 7 — A* z kryterium przesiadek (`ap`)**

```python
def make_astar_transfers_config(graph: Graph, target_ids: set[StopId]) -> SearchConfig:
    # Prekomputacja: które kursy docierają do stacji docelowej?
    trips_to_target: set[str] = set()
    for conns in graph.values():
        for conn in conns:
            if conn.to_stop_id in target_ids:
                trips_to_target.add(conn.trip_id)             # (1)

    def heuristic(state: tuple, _target_ids) -> int:
        stop_id, trip_id = state
        if stop_id in target_ids:
            return 0                                           # (2)
        if trip_id is not None and trip_id in trips_to_target:
            return 0                                           # (3)
        return 1                                               # (4)

    config = make_transfers_config()
    config.heuristic = heuristic
    config.make_f = lambda cost, h: (cost[0] + h, cost[1])   # (5)
    return config
```

- **(1)** Prekomputacja w $O(|E|)$ — dla każdej krawędzi kończącej się w celu zapisujemy `trip_id`.
- **(2)** Już na miejscu — 0 przesiadek więcej.
- **(3)** Obecny kurs ma zatrzymanie w stacji docelowej — dotrzemy bez przesiadki.
- **(4)** Obecny kurs nie dociera do celu — konieczna co najmniej 1 przesiadka.
- **(5)** `make_f` definiuje jak dodać heurystykę do krotki kosztu — dodajemy tylko do składowej przesiadkowej, nie do czasu.

---

**Fragment 8 — wspólny algorytm wyszukiwania**

```python
def search(graph, source_ids, target_ids, departure_time, config):
    h = config.heuristic

    best_cost: dict[State, Cost] = {}
    prev: dict[State, tuple[State, Connection] | None] = {}
    queue = []
    counter = itertools.count()    # (1)

    for cost, state in config.initial_states(source_ids, departure_time):
        best_cost[state] = cost
        prev[state] = None
        if h:
            h_val = h(state, target_ids)
            f = config.make_f(cost, h_val) if config.make_f else cost + h_val
        else:
            f = cost                                           # (2)
        heapq.heappush(queue, (f, next(counter), cost, state))

    while queue:
        _, _, current_cost, current_state = heapq.heappop(queue)

        if current_cost != best_cost.get(current_state):      # (3)
            continue

        if config.is_goal(current_state, target_ids):
            return _build_result(...), step                    # (4)

        for new_cost, new_state, conn in config.expand(current_state, current_cost, graph):
            if new_state not in best_cost or new_cost < best_cost[new_state]:
                best_cost[new_state] = new_cost
                prev[new_state] = (current_state, conn)
                if h:
                    h_val = h(new_state, target_ids)
                    new_f = config.make_f(new_cost, h_val) if config.make_f else new_cost + h_val
                else:
                    new_f = new_cost
                heapq.heappush(queue, (new_f, next(counter), new_cost, new_state))  # (5)

    return None, step
```

- **(1)** `itertools.count()` jako tiebreaker — gdy dwa węzły mają równe $f$, heap porównuje kolejny element krotki. Counter gwarantuje unikalność i unika błędu porównywania stanów.
- **(2)** Gdy brak heurystyki (`None`), priorytet = koszt = klasyczna Dijkstra.
- **(3)** Lazy deletion — zamiast aktualizować istniejące wpisy w heap (kosztowne), dodajemy nowy wpis i ignorujemy zdezaktualizowane. Wpis jest zdezaktualizowany gdy `current_cost != best_cost[state]`.
- **(4)** Algorytm kończy się gdy cel **wychodzi z kolejki** — nie gdy jest do niej dodany. Gwarantuje optymalność: gdy cel jest na szczycie kolejki, żadna inna ścieżka nie może być lepsza.
- **(5)** `prev[new_state] = (current_state, conn)` przechowuje poprzedni stan i krawędź — umożliwia rekonstrukcję ścieżki przez cofanie się po `prev`.

---

## 3. Wyniki

Testy wykonano na danych Kolei Dolnośląskich, poniedziałek. Kryterium: `t` = Dijkstra czas, `p` = Dijkstra przesiadki, `at` = A* czas (euklid), `ats` = A* czas (rev-Dijkstra), `ap` = A* przesiadki.

### 3.1 Wrocław Główny → Jelenia Góra, odjazd 10:00

**Wyniki wyszukiwania:**

| Kryterium | Odjazd | Przyjazd | Przesiadki | Linie | Węzły |
|---|---|---|---|---|---|
| `t` | 10:10 | 12:26 | 0 | D6 | 207 |
| `p` | 10:10 | 12:26 | 0 | D6 | 440 |
| `at` | 10:10 | 12:26 | 0 | D6 | 145 |
| `ats` | 10:10 | 12:26 | 0 | D6 | 49 |
| `ap` | 10:10 | 12:26 | 0 | D6 | 44 |

**Trasa (wszystkie kryteria identyczne):**
```
Wrocław Główny → Jelenia Góra  [D6]  10:10 → 12:26
```

**Redukcja odwiedzonych węzłów względem Dijkstry (`t`):**

| Algorytm | Węzły | Redukcja |
|---|---|---|
| Dijkstra `t` | 207 | — |
| A* euklid `at` | 145 | −30% |
| A* rev-Dijkstra `ats` | 49 | −76% |
| A* przesiadki `ap` | 44 | −79% |

Trasa bezpośrednia — wszystkie algorytmy zwracają ten sam wynik. `ap` odwiedza najmniej węzłów, bo heurystyka natychmiast rozpoznaje że D6 dociera do celu (h=0) i nadaje mu najwyższy priorytet.

---

### 3.2 Wrocław Główny → Legnica, odjazd 08:30

**Wyniki wyszukiwania:**

| Kryterium | Odjazd | Przyjazd | Przesiadki | Linie | Węzły |
|---|---|---|---|---|---|
| `t` | 08:43 | 09:45 | 1 | D2, D1 | 70 |
| `p` | 08:49 | 09:45 | **0** | D1 | 95 |
| `at` | 08:43 | 09:45 | 1 | D2, D1 | 43 |
| `ats` | 08:43 | 09:45 | 1 | D2, D1 | 28 |
| `ap` | 08:49 | 09:45 | **0** | D1 | 20 |

**Trasa kryterium czasu (`t`, `at`, `ats`):**
```
Wrocław Główny → Wrocław Muchobór  [D2]  08:43 → 08:48
Wrocław Muchobór → Legnica          [D1]  08:54 → 09:45
```

**Trasa kryterium przesiadek (`p`, `ap`):**
```
Wrocław Główny → Legnica  [D1]  08:49 → 09:45
```

Kryteria czasu i przesiadek dają różne trasy — kryterium czasu wybiera wcześniejszy odjazd (08:43) kosztem przesiadki, kryterium przesiadek czeka 6 minut na bezpośredni pociąg D1 (08:49). Czas przyjazdu identyczny.

---

### 3.3 Wrocław Główny → Karpacz, odjazd 15:20

**Wyniki wyszukiwania:**

| Kryterium | Odjazd | Przyjazd | Przesiadki | Linie | Węzły |
|---|---|---|---|---|---|
| `t` | 15:40 | 18:53 | 2 | D6, D6, D62 | 267 |
| `p` | 15:55 | 18:53 | **1** | D6, D62 | 6175 |
| `at` | 15:40 | 18:53 | 2 | D6, D6, D62 | 250 |
| `ats` | 15:40 | 18:53 | 2 | D6, D6, D62 | 144 |
| `ap` | 15:55 | 18:53 | **1** | D6, D62 | 928 |

**Trasa kryterium czasu (`t`, `at`, `ats`):**
```
Wrocław Główny → Wałbrzych Miasto  [D6]   15:40 → 16:46
Wałbrzych Miasto → Jelenia Góra    [D6]   17:01 → 18:10  (zmiana składu)
Jelenia Góra → Karpacz             [D62]  18:35 → 18:53
```

**Trasa kryterium przesiadek (`p`, `ap`):**
```
Wrocław Główny → Jelenia Góra  [D6]   15:55 → 18:10
Jelenia Góra → Karpacz         [D62]  18:35 → 18:53
```

Mimo tej samej nazwy linii D6, w trasie czasowej są to dwa różne `trip_id` — zmiana składu w Wałbrzychu liczy się jako przesiadka. Kryterium przesiadek czeka na D6 o 15:55, który jedzie jako jeden kurs aż do Jeleniej Góry.

`p` (Dijkstra przesiadki) odwiedza 6175 węzłów vs 928 dla `ap` (A* przesiadki) — heurystyka binarna redukuje przeszukiwanie ~6.6×.

---

### 3.4 Kłodzko Główne → Zgorzelec, odjazd 06:00

**Wyniki wyszukiwania:**

| Kryterium | Odjazd | Przyjazd | Przesiadki | Linie | Węzły |
|---|---|---|---|---|---|
| `t` | 06:06 | 09:54 | 3 | D9, D91, D1, D10 | 238 |
| `p` | 06:06 | 09:54 | **1** | D9, D10 | 1537 |
| `at` | 06:06 | 09:54 | 3 | D9, D91, D1, D10 | 200 |
| `ats` | 06:06 | 09:54 | 3 | D9, D91, D1, D10 | 109 |
| `ap` | 06:06 | 09:54 | **1** | D9, D10 | 177 |

**Trasa kryterium czasu (`t`, `at`, `ats`):**
```
Kłodzko Główne → Kamieniec Ząbkowicki  [D9]   06:06 → 06:23
Kamieniec Ząbkowicki → Legnica          [D91]  06:31 → 08:37
Legnica → Węgliniec                     [D1]   08:43 → 09:33
Węgliniec → Zgorzelec                   [D10]  09:38 → 09:54
```

**Trasa kryterium przesiadek (`p`, `ap`):**
```
Kłodzko Główne → Wrocław Główny  [D9]   06:06 → 07:27
Wrocław Główny → Zgorzelec       [D10]  08:21 → 09:54
```

Na dłuższych trasach różnica między kryteriami jest wyraźna — 3 przesiadki vs 1 przy identycznym czasie przyjazdu. Heurystyka `ats` redukuje węzły o 54% względem Dijkstry.

---

### 3.5 Zbiorcze porównanie odwiedzonych węzłów

| Trasa | `t` | `at` | `ats` | redukcja `ats` | `p` | `ap` | redukcja `ap` |
|---|---|---|---|---|---|---|---|
| Wrocław → Jelenia Góra | 207 | 145 | 49 | **−76%** | 440 | 44 | **−90%** |
| Wrocław → Legnica | 70 | 43 | 28 | **−60%** | 95 | 20 | **−79%** |
| Wrocław → Karpacz | 267 | 250 | 144 | **−46%** | 6175 | 928 | **−85%** |
| Kłodzko → Zgorzelec | 238 | 200 | 109 | **−54%** | 1537 | 177 | **−88%** |

Heurystyka oparta na odwróconej Dijkstrze (`ats`) redukuje przeszukiwanie o 46–76% względem Dijkstry. Heurystyka binarna dla przesiadek (`ap`) osiąga redukcję 79–90% względem Dijkstry przesiadkowej.

---

## 4. Użyte biblioteki

| Biblioteka | Zastosowanie |
|---|---|
| `heapq` (stdlib) | Kolejka priorytetowa w Dijkstrze i A* |
| `csv` (stdlib) | Parsowanie plików GTFS (.txt) |
| `datetime` (stdlib) | Obliczanie dnia tygodnia, filtrowanie kalendarza |
| `math` (stdlib) | Obliczanie odległości euklidesowej dla heurystyki `at` |
| `collections.defaultdict` (stdlib) | Budowanie grafu sąsiedztwa i grafu odwróconego |
| `itertools` (stdlib) | Generator liczników jako tiebreaker w kolejce |
| `folium` | Generowanie interaktywnej mapy HTML z wynikiem trasy |

Implementacja nie wymaga żadnych zewnętrznych zależności poza `folium` (wizualizacja).

---

## 5. Napotkane problemy

**Czasy powyżej 24:00** — format GTFS dopuszcza godziny takie jak `25:10:00` dla kursów realizowanych po północy. Standardowa biblioteka `datetime` nie obsługuje takich wartości. Rozwiązanie: reprezentacja czasu jako liczba sekund od północy (`int`), bez użycia obiektów `time`.

**Kursy przekraczające północ** — kurs odjeżdżający o 23:50 i przyjeżdżający o 00:30 następnego dnia wymaga załadowania rozkładu dla dwóch dni. Rozwiązanie: wczytanie kursów następnego dnia z `time_offset=86400` sekund i dołączenie ich do grafu.

**Normalizacja peronów** — plik `stops.txt` zawiera zarówno stacje (`location_type=1`) jak i perony (`location_type=0`). Bez normalizacji przesiadka między peronami tej samej stacji byłaby niemożliwa. Rozwiązanie: mapowanie każdego peronu do `parent_station`.

**Przystanki tylko do wysiadania** — niektóre przystanki mają `pickup_type=1` (brak możliwości wsiadania). Bez filtrowania tworzyłyby krawędzie wychodzące z przystanków, z których pasażer nie może odjechać. Rozwiązanie: pomijanie takich krawędzi przy budowaniu grafu.
