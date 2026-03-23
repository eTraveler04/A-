from datetime import date, timedelta

DAY_NAMES: dict[str, int] = {
    "poniedzialek": 0, "pon": 0, "monday": 0,    "1": 0,
    "wtorek":       1, "wt":  1, "tuesday": 1,   "2": 1,
    "sroda":        2, "sr":  2, "wednesday": 2, "3": 2,
    "czwartek":     3, "cz":  3, "thursday": 3,  "4": 3,
    "piatek":       4, "pt":  4, "friday": 4,    "5": 4,
    "sobota":       5, "so":  5, "saturday": 5,  "6": 5,
    "niedziela":    6, "nd":  6, "sunday": 6,    "7": 6,
}


def weekday_to_date(weekday: int) -> date:
    """Zwraca najbliższą datę (dzisiaj lub w przyszłości) dla podanego dnia tygodnia (0=pon)."""
    today = date.today()
    days_ahead = (weekday - today.weekday()) % 7
    return today + timedelta(days=days_ahead)


def parse_day(day_str: str) -> date:
    key = day_str.lower().strip()
    if key not in DAY_NAMES:
        raise ValueError(f"Nieznany dzień tygodnia: '{day_str}'")
    return weekday_to_date(DAY_NAMES[key])
