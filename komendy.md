# Komendy

## Dijkstra — czas
```
python main.py "Wrocław Główny" "Karpacz" t "15:20" "pon"
```
```
python main.py "Wrocław Główny" "Legnica" t "08:30" "pon"
```
```
python main.py "Wrocław Główny" "Jelenia Góra" t "10:00" "pon"
```

## Dijkstra — przesiadki
```
python main.py "Wrocław Główny" "Karpacz" p "15:20" "pon"
```
```
python main.py "Wrocław Główny" "Legnica" p "08:30" "pon"
```
```
python main.py "Wrocław Główny" "Jelenia Góra" p "10:00" "pon"
```

## A* — czas
```
python main.py "Wrocław Główny" "Karpacz" at "15:20" "pon"
```
```
python main.py "Wrocław Główny" "Legnica" at "08:30" "pon"
```
```
python main.py "Wrocław Główny" "Jelenia Góra" at "10:00" "pon"
```

## A* — czas (ulepszona heurystyka)
```
python main.py "Wrocław Główny" "Karpacz" ats "15:20" "pon"
```
```
python main.py "Wrocław Główny" "Legnica" ats "08:30" "pon"
```
```
python main.py "Wrocław Główny" "Jelenia Góra" ats "10:00" "pon"
```

## A* — przesiadki
```
python main.py "Wrocław Główny" "Karpacz" ap "15:20" "pon"
```
```
python main.py "Wrocław Główny" "Legnica" ap "08:30" "pon"
```
```
python main.py "Wrocław Główny" "Jelenia Góra" ap "10:00" "pon"
```


python main.py "Lubawka" "Rokitki" t "8:40" "pt"

## Tabu Search — czas (wariant a, bazowy)
```
python main2.py "Wrocław Główny" "Legnica;Jelenia Góra" t "08:30" "pon"
```
```
python main2.py "Wrocław Główny" "Legnica;Karpacz" t "08:30" "pon"
```
```
python main2.py "Wrocław Główny" "Legnica;Jelenia Góra;Karpacz" t "08:30" "pon"
```

## Tabu Search — przesiadki (wariant a, bazowy)
```
python main2.py "Wrocław Główny" "Legnica;Jelenia Góra" p "08:30" "pon"
```
```
python main2.py "Wrocław Główny" "Legnica;Karpacz" p "08:30" "pon"
```

## Tabu Search — zmienny rozmiar T (wariant b)
```
python main2.py "Wrocław Główny" "Legnica;Jelenia Góra;Karpacz" t "08:30" "pon" --tabu-size auto
```

## Tabu Search — aspiracja (wariant c)
```
python main2.py "Wrocław Główny" "Legnica;Jelenia Góra" p "08:30" "pon" --aspiration
```
```
python main2.py "Wrocław Główny" "Legnica;Jelenia Góra;Karpacz" t "08:30" "pon" --aspiration
```

## Tabu Search — próbkowanie sąsiedztwa (wariant d)
```
python main2.py "Wrocław Główny" "Legnica;Jelenia Góra;Karpacz" t "08:30" "pon" --sample 3
```

## Tabu Search — wszystkie warianty razem
```
python main2.py "Wrocław Główny" "Legnica;Jelenia Góra;Karpacz" t "08:30" "pon" --tabu-size auto --aspiration --sample 3
```
python main2.py "Wrocław Główny" "Legnica;Jelenia Góra;Karpacz" t "08:30" "pon" --tabu-size auto --aspiration --sample 3
