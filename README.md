# 🤖 AI Agents System

> System wieloagentowy do automatyzacji zadań, generowania kodu i orkiestracji procesów oparty na Python i OpenAI.
>
> Multi-agent system for task automation, code generation, and process orchestration built on Python and OpenAI.

---

## Spis treści / Table of Contents

- [Opis projektu / Project Overview](#opis-projektu--project-overview)
- [Architektura / Architecture](#architektura--architecture)
- [Agenci / Agents](#agenci--agents)
- [Instalacja / Installation](#instalacja--installation)
- [Konfiguracja / Configuration](#konfiguracja--configuration)
- [Uruchomienie / Running](#uruchomienie--running)
- [Testy / Tests](#testy--tests)
- [Agent dokumentacji / Docs Agent](#agent-dokumentacji--docs-agent)
- [Rozszerzanie / Extending](#rozszerzanie--extending)
- [Zależności / Dependencies](#zależności--dependencies)

---

## Opis projektu / Project Overview

**PL** — Framework do tworzenia i orkiestrowania autonomicznych agentów AI. Główny orkiestrator przyjmuje zadania, priorytetyzuje je (skala 1–10) i deleguje do wyspecjalizowanych agentów wykonujących je współbieżnie przez `asyncio`. Każdy agent dziedziczy z `BaseAgent` i implementuje jedną metodę `_process_task`.

**EN** — A framework for building and orchestrating autonomous AI agents. The main orchestrator accepts tasks, prioritises them (scale 1–10), and delegates them to specialised agents that execute concurrently via `asyncio`. Every agent inherits from `BaseAgent` and implements a single `_process_task` method.

---

## Architektura / Architecture

```
Użytkownik / User
       |
       v
 OrchestratorAgent          <-- rejestruje agentów / registers agents
       |
       v
  Kolejka zadań             <-- sortowana po priorytecie / sorted by priority
  Task Queue
       |
       v
 asyncio.gather()           <-- równoległe wykonanie / parallel execution
  /    |    |    \
 v     v    v     v
CodeGen  Researcher  TaskExec  Analyst
       |
       v
  Agregacja wyników / Result aggregation
```

---

## Agenci / Agents

### OrchestratorAgent
**PL** — Główny koordynator systemu. Rejestruje agentów, zarządza kolejką zadań, deleguje pracę i zbiera wyniki. Uruchamia wszystkie zadania równolegle przez `asyncio.gather()`.

**EN** — The central coordinator. Registers agents, manages the task queue, delegates work, and aggregates results. Runs all tasks in parallel via `asyncio.gather()`.

```python
orchestrator.register_agent(AgentType.CODE_GENERATOR, code_gen_agent)
await orchestrator.submit_task(task)          # adds to priority queue
await orchestrator.execute(orchestration_task) # runs all queued tasks
await orchestrator.get_orchestration_status()  # current state
```

---

### CodeGeneratorAgent
**PL** — Generuje kod na podstawie opisu zadania. Obsługuje dowolny język programowania przekazany w parametrach zadania (`language`, `framework`).

**EN** — Generates code from a task description. Supports any programming language passed via task parameters (`language`, `framework`).

```python
Task(
    id="task_001",
    name="Generate REST API",
    description="Generate a Python REST API with FastAPI",
    agent_type=AgentType.CODE_GENERATOR,
    parameters={"language": "python", "framework": "fastapi"},
    priority=10
)
```

---

### ResearcherAgent
**PL** — Zbiera i opracowuje informacje na wskazany temat. Zwraca listę wyników i źródeł.

**EN** — Gathers and processes information on a given topic. Returns a list of findings and sources.

```python
Task(
    id="task_002",
    name="Research Python Best Practices",
    description="Research and compile Python best practices",
    agent_type=AgentType.RESEARCHER,
    parameters={"topic": "python best practices"},
    priority=8
)
```

---

### TaskExecutorAgent
**PL** — Wykonuje zadania systemowe i polecenia. Przyjmuje parametr `command` i zwraca wynik wykonania.

**EN** — Executes system tasks and commands. Accepts a `command` parameter and returns the execution output.

```python
Task(
    id="task_003",
    name="Run script",
    description="Execute a shell command",
    agent_type=AgentType.TASK_EXECUTOR,
    parameters={"command": "echo hello"},
    priority=7
)
```

---

### AnalystAgent
**PL** — Analizuje dane i generuje raporty z wnioskami (`insights`). Przyjmuje listę metryk do analizy.

**EN** — Analyses data and generates reports with insights. Accepts a list of metrics to analyse.

```python
Task(
    id="task_004",
    name="Analyze Project Metrics",
    description="Analyse project performance metrics",
    agent_type=AgentType.ANALYST,
    parameters={"metrics": ["performance", "code_quality"]},
    priority=5
)
```

---

## Instalacja / Installation

### Wymagania / Requirements
- Python **3.12+**
- [Poetry](https://python-poetry.org/) — zarządzanie zależnościami / dependency manager
- Klucz API OpenAI / OpenAI API key

### Kroki / Steps

```bash
# 1. Przejdź do katalogu projektu / Go to the project directory
cd path/to/Agents

# 2. Zainstaluj zależności przez Poetry / Install dependencies via Poetry
poetry install

# 3. Skopiuj plik zmiennych środowiskowych / Copy the env template
cp .env.example .env

# 4. Uzupełnij klucz API w .env / Fill in your API key in .env
#    OPENAI_API_KEY=sk-...
```

---

## Konfiguracja / Configuration

Plik `.env` (na podstawie `.env.example`) / The `.env` file (based on `.env.example`):

```env
# Wymagane / Required
OPENAI_API_KEY=sk-your-key-here

# Opcjonalne / Optional (poniżej wartości domyślne / defaults shown)
DEFAULT_MODEL=gpt-4
TEMPERATURE=0.7
MAX_TOKENS=2000
LOG_LEVEL=INFO
```

Ustawienia ładowane są automatycznie przez `src/config/settings.py` z użyciem `pydantic-settings`.

Settings are loaded automatically by `src/config/settings.py` using `pydantic-settings`.

---

## Uruchomienie / Running

### Główny program / Main program

```bash
# Uruchom przykładowy workflow z wszystkimi agentami
# Run the example workflow with all agents
poetry run python main.py
```

Skrypt tworzy orkiestrator, rejestruje czterech agentów, dodaje trzy przykładowe zadania do kolejki i uruchamia je równolegle.

The script creates an orchestrator, registers four agents, adds three sample tasks to the queue, and runs them in parallel.

### Interaktywnie / Interactively

```bash
poetry shell

python
>>> from src.agents.orchestrator_agent import OrchestratorAgent
>>> from src.agents.specialized_agents import CodeGeneratorAgent
>>> from src.models.agent import AgentConfig, AgentType, Task

# Utwórz agenta / Create an agent
>>> config = AgentConfig(name="Coder", agent_type=AgentType.CODE_GENERATOR, description="Generates code")
>>> agent = CodeGeneratorAgent(config)

# Utwórz zadanie / Create a task
>>> task = Task(id="t1", name="Hello", description="Say hi", agent_type=AgentType.CODE_GENERATOR)

# Uruchom / Execute
>>> import asyncio
>>> result = asyncio.run(agent.execute(task))
>>> print(result)
```

---

## Testy / Tests

```bash
# Uruchom wszystkie testy / Run all tests
poetry run pytest

# Z widocznym outputem / With verbose output
poetry run pytest -v

# Konkretny plik / Specific file
poetry run pytest tests/test_agents.py

# Z pokryciem kodu / With code coverage
poetry run pytest --cov=src
```

Testy znajdują się w `tests/test_agents.py` i obejmują: tworzenie orkiestratora, dodawanie zadań do kolejki oraz sprawdzanie statusu.

Tests live in `tests/test_agents.py` and cover: orchestrator creation, task submission, and status reporting.

---

## Agent dokumentacji / Docs Agent

`docs_agent.py` — niezależny agent, który analizuje zmiany w kodzie (git log / diff) i automatycznie generuje/aktualizuje ten plik README z użyciem OpenAI.

`docs_agent.py` — a standalone agent that analyses code changes (git log / diff) and automatically generates/updates this README using OpenAI.

```bash
# Podstawowe uruchomienie — regeneruje jeśli są zmiany git
# Basic run — regenerates only if git changes are detected
poetry run python docs_agent.py

# Wymuś regenerację bez względu na git
# Force regenerate regardless of git state
poetry run python docs_agent.py --force

# Ostatnie 10 commitów, inny plik wyjściowy
# Last 10 commits, different output file
poetry run python docs_agent.py --since 10 --output DOCS.md

# Inny model OpenAI
# Different OpenAI model
poetry run python docs_agent.py --model gpt-4-turbo --force
```

| Flaga / Flag | Domyślnie / Default | Opis / Description |
|---|---|---|
| `--since N` | `20` | Liczba commitów do analizy / Commits to inspect |
| `--output FILE` | `README.md` | Plik wyjściowy / Output file |
| `--force` | `false` | Regeneruj zawsze / Always regenerate |
| `--model MODEL` | `gpt-4o` | Model OpenAI / OpenAI model |

---

## Rozszerzanie / Extending

### Nowy agent / New agent

```python
# src/agents/specialized_agents.py

class MyCustomAgent(BaseAgent):
    async def _process_task(self, task: Task) -> Any:
        # Twoja logika / Your logic here
        return {"result": "done"}
```

Zarejestruj go w `main.py` / Register it in `main.py`:

```python
orchestrator.register_agent(AgentType.CUSTOM, MyCustomAgent(config))
```

### Nowe narzędzie / New tool

Utwórz klasę w `src/tools/` i udostępnij ją agentom przez `AgentConfig.tools`.

Create a class in `src/tools/` and expose it to agents via `AgentConfig.tools`.

---

## Struktura projektu / Project Structure

```
Agents/
|-- src/
|   |-- agents/
|   |   |-- base_agent.py           # Klasa bazowa / Base class
|   |   |-- orchestrator_agent.py   # Orkiestrator / Orchestrator
|   |   +-- specialized_agents.py   # 4 wyspecjalizowane agenty / 4 specialised agents
|   |-- models/
|   |   +-- agent.py                # Modele Pydantic / Pydantic models
|   |-- tools/
|   |   |-- code_executor.py        # Wykonanie kodu / Code execution
|   |   +-- file_tools.py           # Operacje na plikach / File operations
|   +-- config/
|       +-- settings.py             # Konfiguracja z .env / Config from .env
|-- tests/
|   +-- test_agents.py              # Testy jednostkowe / Unit tests
|-- main.py                         # Punkt wejścia / Entry point
|-- docs_agent.py                   # Agent dokumentacji / Docs agent
|-- pyproject.toml                  # Konfiguracja Poetry
+-- .env.example                    # Szablon zmiennych / Env template
```

---

## Zależności / Dependencies

| Pakiet | Wersja | Zastosowanie / Usage |
|---|---|---|
| `openai` | >=2.31.0 | API OpenAI dla agentów / OpenAI API for agents |
| `pydantic` | >=2.12.5 | Modele danych i walidacja / Data models & validation |
| `pydantic-settings` | >=2.0.0 | Konfiguracja z `.env` / Config from `.env` |
| `langchain` | >=1.2.15 | Framework LLM / LLM framework |
| `python-dotenv` | >=1.2.2 | Wczytywanie `.env` / Loading `.env` |
| `requests` | >=2.33.1 | Zapytania HTTP / HTTP requests |
| `pytest` | >=9.0.3 | Testy *(dev)* |
| `pytest-asyncio` | >=1.3.0 | Testy async *(dev)* |

---

## Licencja / License

MIT

---

*Dokumentacja generowana automatycznie przez `docs_agent.py` / Documentation automatically maintained by `docs_agent.py`*
