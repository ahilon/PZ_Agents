# Trip Planner Agent

Agent do automatycznego generowania planów podróży w formacie `.docx`.

Użytkownik opisuje wycieczkę w pliku Markdown — agent planuje optymalną trasę, szacuje czasy i koszty, generuje gotowy dokument.

---

## Jak to działa

```
trips/moja_wycieczka.md   ←  użytkownik wypełnia
        ↓
TripPlannerAgent
        ↓  GPT-4o
  • optymalizuje trasę dzienną (geografia)
  • szacuje czas każdej atrakcji
  • dobiera transport między punktami (pieszo / metro / taxi)
  • sprawdza orientacyjne koszty wejść
  • przelicza waluty na PLN
        ↓
plan_Wycieczka_do_Barcelony.docx
```

---

## Struktura wyjściowego dokumentu

| Sekcja | Zawartość |
|---|---|
| **Transport** | tabela: odcinek, typ, trasa, data/godzina, numer, koszt, czy zapłacone, link Google Maps |
| **Noclegi** | tabela: nazwa, adres, check-in, check-out, liczba nocy, koszt, link Google Maps |
| **Plan dnia** | osobna sekcja na każdy dzień z tabelą atrakcji |
| **Podsumowanie kosztów** | tabela ze wszystkimi wydatkami, przelicznik na PLN |

### Priorytety atrakcji

| Priorytet | Znaczenie | Jak trafia do planu |
|---|---|---|
| `[P1]` | Obowiązkowe | Zawsze w planie, ułożone geograficznie |
| `[P2]` | Bardzo chcemy | Dodawane jeśli zostaje czas po P1 |
| `[P3]` | Warto wpaść | Sugestia "po drodze" między krokami P1/P2 |

---

## Wypełnianie pliku wejściowego

Skopiuj plik `trips/przyklad.md` i uzupełnij swoimi danymi.

### Minimalna struktura

```markdown
# Wycieczka do Pragi

## Informacje ogólne
- **Daty:** 10.06.2025 — 13.06.2025
- **Liczba osób:** 2
- **Waluta lokalna:** CZK

## Transport

### Podróż tam
- Typ: autobus
- Skąd: Warszawa (Dworzec Zachodni)
- Dokąd: Praga (Florenc)
- Data i godzina: 10.06.2025 07:00
- Numer: FlixBus 123
- Koszt: 80 PLN/os (zapłacone: tak)

## Noclegi

### Hostel One Miru
- Adres: Cimburkova 8, Praga
- Check-in: 10.06.2025 od 14:00
- Check-out: 13.06.2025 do 11:00
- Liczba nocy: 3
- Koszt: 150 EUR łącznie (zapłacone: nie)

## Plan dnia

### Dzień 1 — 10.06.2025
- [P1] Stare Miasto — Rynek Staromiejski
- [P1] Zegar astronomiczny
- [P2] Most Karola
- [P3] Małá Strana — kawiarnie

## Budżet dodatkowy
- Wyżywienie: 30 EUR/os/dzień
- Transport lokalny: 5 EUR/os/dzień
```

### Wskazówki do wypełniania

**Transport:**
- Podaj numer lotu/pociągu/autobusu jeśli masz — trafi do dokumentu
- Koszt możesz podać w dowolnej walucie — agent przeliczy na PLN
- `(zapłacone: tak/nie)` — trafi do tabeli kosztów

**Noclegi:**
- Podaj pełny adres — agent wygeneruje link Google Maps
- Możesz dodać kilka noclegów (np. różne hotele w różnych miastach)

**Plan dnia:**
- Każdy dzień zaczyna się od `### Dzień N — DD.MM.YYYY`
- Opcjonalnie dodaj opis dnia po `—` np. `— Stare Miasto`
- Atrakcje oznaczaj `[P1]`, `[P2]`, `[P3]` — kolejność nie ma znaczenia, agent posortuuje geograficznie
- Krótki opis po `—` pomaga agentowi lepiej zrozumieć atrakcję

---

## Uruchomienie

### Opcja 1 — przez run_project.py

Utwórz plik projektu (np. `projekt_barcelona.md`):

```markdown
# Plan Barcelony

## Zadania

- Wygeneruj plan podróży z pliku trips/barcelona.md
  - agent: trip_planner
  - trip_file: trips/barcelona.md
  - output_path: output/barcelona.docx
```

Uruchom:

```bash
poetry run python run_project.py projekt_barcelona.md --only trip_planner
```

### Opcja 2 — bezpośrednio w kodzie Python

```python
import asyncio
from agents.trip_planner_agent import TripPlannerAgent
from src.models.agent import AgentConfig, AgentType, Task

async def main():
    agent = TripPlannerAgent(AgentConfig(
        name="Trip Planner",
        agent_type=AgentType.TRIP_PLANNER,
        description="Planuje podróże",
        system_prompt="",
    ))

    task = Task(
        id="trip_001",
        name="Plan Barcelony",
        description="Generuj plan podróży",
        agent_type=AgentType.TRIP_PLANNER,
        parameters={
            "trip_file": "trips/przyklad.md",
            "output_path": "output/barcelona.docx",
            # opcjonalnie:
            # "model": "gpt-4o",
            # "trip_text": "...",  # zamiast trip_file
        },
    )

    response = await agent.execute(task)
    if response.success:
        print(f"Gotowe: {response.result['output_path']}")
    else:
        print(f"Błąd: {response.error}")

asyncio.run(main())
```

---

## Parametry zadania

| Parametr | Typ | Wymagany | Opis |
|---|---|---|---|
| `trip_file` | `str` | tak* | Ścieżka do pliku `.md` z opisem podróży |
| `trip_text` | `str` | tak* | Opis podróży jako tekst (alternatywa dla `trip_file`) |
| `output_path` | `str` | nie | Ścieżka wyjściowego `.docx` (domyślnie: `plan_<nazwa>.docx`) |
| `model` | `str` | nie | Model OpenAI (domyślnie: `gpt-4o`) |

*Wymagany `trip_file` lub `trip_text` — jedno z dwóch.

---

## Wymagania

```bash
# Biblioteki (powinny być już zainstalowane)
poetry add python-docx

# Zmienna środowiskowa
OPENAI_API_KEY=sk-...
```

---

## Przykładowy wynik

Po uruchomieniu na `trips/przyklad.md` (wycieczka do Barcelony, 5 dni):

```
plan_Wycieczka_do_Barcelony.docx
├── WYCIECZKA DO BARCELONY
│   15-20.05.2025  •  2 os.
│
├── TRANSPORT
│   ┌──────────────┬──────────┬───────────────────┬─────────────────┐
│   │ Podróż tam   │ samolot  │ WAW → BCN         │ 15.05 06:30     │
│   │ Powrót       │ samolot  │ BCN → WAW         │ 20.05 21:00     │
│   └──────────────┴──────────┴───────────────────┴─────────────────┘
│
├── NOCLEGI
│   ┌──────────────────────┬──────────────────────┬──────┬──────────┐
│   │ Hotel Arts Barcelona │ 15.05 od 15:00       │  5   │ 900 EUR  │
│   └──────────────────────┴──────────────────────┴──────┴──────────┘
│
├── PLAN DNIA
│   Dzień 1 — 15.05.2025 — Przybycie i Sagrada Familia
│   ┌─────┬──────────────────┬──────┬───────────────────┬──────────┐
│   │ P1  │ Sagrada Familia  │ 2.0h │ metro L5, 20 min  │ 26 EUR   │
│   │ P1  │ Park Güell       │ 1.5h │ bus 24, 15 min    │ 10 EUR   │
│   │ P2  │ Casa Batlló      │ 1.5h │ pieszo, 10 min    │ 35 EUR   │
│   │ P3  ↳ Passeig de Gràcia│      │ po drodze         │ bezpł.   │
│   └─────┴──────────────────┴──────┴───────────────────┴──────────┘
│   → Łącznie ok. 9h aktywności. Szacowany koszt atrakcji: ~71 EUR/os
│
└── PODSUMOWANIE KOSZTÓW
    ┌─────────────┬────────────────────────────┬──────┬─────────┬──────────┐
    │ Transport   │ Lot WAW→BCN + powrót (×2)  │  ✓  │ 1600 PLN│ 1600 PLN │
    │ Nocleg      │ Hotel Arts, 5 nocy         │  —  │ 900 EUR │ 3825 PLN │
    │ Atrakcje    │ Szacunkowo (5 dni)         │  —  │ ~750 EUR│ 3188 PLN │
    │ Wyżywienie  │ 50 EUR/os/dzień × 2 × 5   │  —  │ 500 EUR │ 2125 PLN │
    │ RAZEM       │                            │     │         │~10 738 PLN│
    └─────────────┴────────────────────────────┴──────┴─────────┴──────────┘
```

---

## Znane ograniczenia

- **Koszty atrakcji** — orientacyjne, na podstawie wiedzy modelu. Zawsze weryfikuj przed wyjazdem.
- **Czasy transportu** — szacunkowe, nie uwzględniają korków ani opóźnień.
- **Kursy walut** — przybliżone (wiedza modelu). Dla dokładnych przeliczeń dodaj aktualny kurs w pliku wejściowym: `- Kurs EUR/PLN: 4.28`
- **Google Maps** — linki generowane jako zapytania tekstowe (`/maps/search/`), nie jako konkretne adresy URL miejsc. Działają, ale mogą wymagać doprecyzowania.
- **Google Docs** — nie jest obsługiwane. Wyjściem jest `.docx`, który można ręcznie zaimportować do Google Docs (`Plik → Importuj`).
