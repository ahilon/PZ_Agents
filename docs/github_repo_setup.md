# Konfiguracja nowego repozytorium GitHub

Instrukcja tworzenia bezpiecznego repo od zera — ochrona `main`, wymuszenie PR, uprawnienia.

---

## 1. Tworzenie repozytorium

Wejdź na **github.com → New repository** i ustaw:

| Pole | Wartość |
|---|---|
| Repository name | `nazwa-projektu` |
| Visibility | Public / Private (wg potrzeb) |
| Initialize with README | ❌ (jeśli masz lokalny kod do wypchnięcia) |
| Add .gitignore | ❌ (masz własny) |
| Choose a license | wg potrzeb |

> Jeśli inicjujesz lokalne repo i chcesz je wypchnąć — **nie inicjalizuj na GitHubie**, bo będzie konflikt przy pierwszym pushu.

---

## 2. Lokalny init i pierwszy push

```bash
cd twoj-projekt/

git init -b main
git add .
git commit -m "chore: initial commit"
git remote add origin https://github.com/OWNER/REPO.git
git push -u origin main
```

---

## 3. Ochrona gałęzi `main` — Branch Ruleset

> **Settings → Rules → Rulesets → New ruleset → New branch ruleset**

### 3.1 Podstawowe ustawienia

| Pole | Wartość |
|---|---|
| Ruleset name | `protect-main` |
| Enforcement status | **Active** |
| Target branches | Include by pattern → `main` |

### 3.2 Reguły — co włączyć

| Reguła | Ustawienie | Po co |
|---|---|---|
| **Restrict creations** | ✅ | Nikt nie może tworzyć gałęzi o nazwie `main` od nowa |
| **Restrict deletions** | ✅ | Nikt nie może usunąć gałęzi `main` |
| **Block force pushes** | ✅ | Zakaz `git push --force` na `main` |
| **Require a pull request before merging** | ✅ | Każda zmiana musi przejść przez PR |
| — Required approvals | `1` | Co najmniej 1 osoba musi zatwierdzić PR |
| — Dismiss stale pull request approvals | ✅ | Nowy commit w PR kasuje poprzednie zatwierdzenia |
| — Require review from Code Owners | ❌ (opcjonalne) | Tylko jeśli masz plik `CODEOWNERS` |
| **Require status checks to pass** | ✅ | Włącz — mamy CI z pylint + isort |
| **Require signed commits** | ❌ (opcjonalne) | Włącz jeśli chcesz weryfikacji GPG |

### 3.3 Bypass list (kto może ominąć reguły)

W sekcji **Bypass list** dodaj siebie jako `Role: Repository admin` jeśli chcesz mieć możliwość awaryjnego pusha bezpośrednio.

> ⚠️ Jeśli **nie** dodasz się do bypass list — Ty też będziesz musiał robić PR. To bezpieczniejsze ustawienie dla pracy zespołowej.

---

## 4. Uprawnienia współpracowników

> **Settings → Collaborators → Add people**

| Rola | Co może |
|---|---|
| **Read** | Tylko klonowanie i przeglądanie |
| **Triage** | Zarządzanie Issues/PR, bez push |
| **Write** | Push na gałęzie (nie `main`), otwieranie PR |
| **Maintain** | Write + zarządzanie repo bez ustawień bezpieczeństwa |
| **Admin** | Pełna kontrola, może mergować mimo reguł (jeśli w bypass list) |

**Bot / agent automatyczny** → rola **Write**
- Może pushować gałęzie `bot/...`
- Nie może pushować do `main`
- Może otwierać PR

---

## 5. Ustawienia ogólne repo

> **Settings → General**

| Opcja | Zalecenie |
|---|---|
| **Wikis** | ❌ wyłącz (jeśli nie używasz) |
| **Issues** | ✅ zostaw |
| **Allow merge commits** | ❌ wyłącz |
| **Allow squash merging** | ✅ zostaw — czysta historia |
| **Allow rebase merging** | ❌ wyłącz (opcjonalne) |
| **Always suggest updating pull request branches** | ✅ |
| **Automatically delete head branches** | ✅ — usuwa gałąź po merge PR |

> Squash merging = wszystkie commity z PR zostają połączone w jeden — czytsza historia `main`.

---

## 6. Secrets (tokeny, klucze API)

> **Settings → Secrets and variables → Actions**

Tutaj przechowuj tokeny używane przez GitHub Actions lub boty:

```
GIT_BOT_TOKEN     → PAT konta bota
OPENAI_API_KEY    → klucz API OpenAI
```

Nigdy nie wrzucaj sekretów do kodu. Używaj `.env` lokalnie (wykluczone przez `.gitignore`).

---

## 7. Typowy przepływ pracy po konfiguracji

```
Twój lokalny main (aktualny)
        |
        | git checkout -b feature/moja-zmiana
        v
  Gałąź robocza
        |
        | git add . && git commit -m "feat: opis"
        | git push origin feature/moja-zmiana
        v
  Pull Request na GitHubie
        |
        | Code review (zatwierdzenie)
        v
  Merge do main (Squash)
        |
        v
  Gałąź automatycznie usunięta ✓
```

---

## 8. GitHub Actions CI — pylint + isort

Plik `.github/workflows/quality.yml` uruchamia się automatycznie przy każdym pushu i PR do `main`.

**Co sprawdza:**
- `isort --check-only src/` — czy importy są posortowane
- `pylint src/ --fail-under=7.0` — czy pylint score ≥ 7.0

**Konfiguracja status check (po pierwszym uruchomieniu workflow):**

1. **Settings → Branches** → edytuj ruleset `protect-main`
2. W sekcji **Require status checks to pass** kliknij `Add checks`
3. Wyszukaj: `pylint + isort` (nazwa jobu z workflow)
4. Zaznacz `Require branches to be up to date before merging`

> Status check pojawia się na liście dopiero po pierwszym uruchomieniu CI — wypchnij jakikolwiek PR, poczekaj na wynik, potem dodaj go tutaj.

**Zmiana progu pylint** (plik `.github/workflows/quality.yml`):
```yaml
- name: pylint
  run: poetry run pylint src/ --fail-under=8.0   # zmień próg tutaj
```

**Sekrety GitHub Actions** (jeśli workflow potrzebuje OpenAI):
> Settings → Secrets and variables → Actions → New repository secret

```
OPENAI_API_KEY    → klucz API OpenAI
GIT_BOT_TOKEN     → PAT konta bota (jeśli CI pushuje)
```

---

## 9. Checklist — nowe repo

```
[ ] Repo utworzone bez inicjalizacji (jeśli masz lokalny kod)
[ ] Lokalny git init + pierwszy commit + push
[ ] Branch ruleset "protect-main" aktywny
    [ ] Restrict deletions ✅
    [ ] Block force pushes ✅
    [ ] Require pull request ✅ (min. 1 approval)
    [ ] Dismiss stale reviews ✅
    [ ] Require status checks: "pylint + isort" ✅ (po pierwszym CI run)
[ ] Merge commit wyłączony, Squash merging włączony
[ ] Automatically delete head branches ✅
[ ] .gitignore zawiera .env
[ ] .env.example w repo (bez sekretów)
[ ] .github/workflows/quality.yml w repo ✅
[ ] Sekrety dodane w Settings → Secrets (jeśli potrzebne)
[ ] Bot dodany jako Collaborator (Write) jeśli używany
```
