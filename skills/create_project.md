# Skill: Stwórz projekt

## Kiedy używać
Gdy użytkownik chce stworzyć nowy projekt Python od zera.

---

## Parametry wejściowe
Jeśli użytkownik nie podał któregoś z wymaganych parametrów — zapytaj go o to przed rozpoczęciem.

| Parametr         | Wymagany | Domyślnie              | Opis                                              |
|------------------|----------|------------------------|---------------------------------------------------|
| `project_name`   | ✅       | —                      | Nazwa projektu (snake_case)                       |
| `description`    | ✅       | —                      | Opis projektu — trafi do PROJECT.md i README.md   |
| `repo_path`      | ❌       | `./<project_name>`     | Ścieżka gdzie stworzyć projekt                    |
| `python_version` | ❌       | `3.12`                 | Wersja Pythona (minimum: 3.11.10)                 |

---

## Kolejność kroków

### 1. Sprawdź czy katalog istnieje
Jeśli `repo_path` już istnieje i **nie jest pusty** — zatrzymaj się i zapytaj użytkownika czy kontynuować. Nie nadpisuj istniejącego projektu bez potwierdzenia.

### 2. Utwórz strukturę projektu
```bash
mkdir <repo_path>
cd <repo_path>
poetry init --name <project_name> --python ">=<python_version>" --no-interaction
poetry add --group dev pylint isort pytest pytest-asyncio
mkdir src tests docs
touch src/__init__.py tests/__init__.py
```

### 3. Utwórz `.env.example`
Zawsze twórz plik `.env.example` z placeholderami. Minimum:
```
OPENAI_API_KEY=your_openai_api_key_here
```
Nie twórz `.env` — użytkownik wypełni go sam na podstawie `.env.example`.

### 4. Wywołaj ProjectInitAgent (mode=init)
Parametry:
```json
{
  "mode": "init",
  "repo_path": "<repo_path>",
  "project_name": "<project_name>",
  "description": "<description>"
}
```
Agent stworzy: `.gitignore`, konfigurację pylint/isort w `pyproject.toml`, `PROJECT.md`.

### 5. Wywołaj DocsAgent (--initial)
```bash
poetry run python docs_agent.py --initial
```
Agent wygeneruje `README.md` na podstawie struktury projektu i kodu.

### 6. GitAgent — tylko na wyraźną prośbę
**Nie wywołuj GitAgent automatycznie.** Git init i pierwszy commit wykonuje użytkownik ręcznie lub na wyraźne polecenie. Dopiero po pierwszym commicie kolejne wywołania mogą używać GitAgent do branchy i PR.

---

## Zasady

- Używaj wyłącznie Pythona — żadnych innych języków
- `pyproject.toml` jest obowiązkowy — zawsze twórz przez Poetry
- Zawsze dodawaj do dev: `pylint`, `isort`, `pytest`, `pytest-asyncio`
- Nigdy nie twórz pliku `.env` — tylko `.env.example`
- Nie wywołuj GitAgent jeśli repo nie ma jeszcze żadnego commita

---

## Output

Na końcu wypisz:
1. Strukturę katalogów projektu (tree)
2. Listę stworzonych plików
3. Następne kroki dla użytkownika:
   ```
   Następne kroki:
   1. cp .env.example .env  → uzupełnij klucze API
   2. git init -b main
   3. git add .
   4. git commit -m "chore: initial commit"
   ```
