"""
run_project.py — uruchamia orkiestrator na podstawie pliku Markdown opisującego projekt.

Sposób użycia / Usage:
    poetry run python run_project.py projekt.md
    poetry run python run_project.py projekt.md --exclude researcher,analyst
    poetry run python run_project.py projekt.md --only code_generator,git
    poetry run python run_project.py projekt.md --dry-run
    poetry run python run_project.py projekt.md --model gpt-4o
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI

from src.config.settings import settings
from src.models.agent import AgentConfig, AgentType, Task
from src.agents.orchestrator_agent import OrchestratorAgent
from src.agents.specialized_agents import (
    CodeGeneratorAgent,
    ResearcherAgent,
    TaskExecutorAgent,
    AnalystAgent,
)
from src.agents.git_agent import GitAgent
from src.prompts import (
    ORCHESTRATOR_PROMPT,
    CODE_GENERATOR_PROMPT,
    RESEARCHER_PROMPT,
    TASK_EXECUTOR_PROMPT,
    ANALYST_PROMPT,
    GIT_AGENT_PROMPT,
)

load_dotenv()

logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Mapowanie nazwy → klasa agenta i prompt
AGENT_REGISTRY: dict[AgentType, tuple[type, str, str]] = {
    AgentType.CODE_GENERATOR: (CodeGeneratorAgent, CODE_GENERATOR_PROMPT, "Code Generator"),
    AgentType.RESEARCHER:     (ResearcherAgent,     RESEARCHER_PROMPT,     "Researcher"),
    AgentType.TASK_EXECUTOR:  (TaskExecutorAgent,   TASK_EXECUTOR_PROMPT,  "Task Executor"),
    AgentType.ANALYST:        (AnalystAgent,        ANALYST_PROMPT,        "Analyst"),
    AgentType.GIT:            (GitAgent,            GIT_AGENT_PROMPT,      "Git Agent"),
}

# Prompt parsujący plik MD → lista zadań
MD_PARSER_PROMPT = """Jesteś asystentem parsującym opisy projektów.
Otrzymasz plik Markdown opisujący projekt lub zadania do wykonania.
Twoim zadaniem jest wyodrębnić z niego listę konkretnych zadań i przypisać każde z nich
do odpowiedniego typu agenta.

Dostępne typy agentów:
- code_generator  — pisanie, generowanie lub refaktoryzacja kodu
- researcher      — zbieranie informacji, badanie tematu, dokumentacja
- task_executor   — uruchamianie poleceń, skryptów, procedur systemowych
- analyst         — analiza danych, metryk, wyników, generowanie raportów
- git             — operacje git: inicjalizacja repo lub tworzenie commitów

Zwróć WYŁĄCZNIE poprawny JSON w tym formacie (bez żadnego tekstu przed ani po):
[
  {
    "id": "task_001",
    "name": "Krótka nazwa zadania",
    "description": "Szczegółowy opis co należy zrobić",
    "agent_type": "code_generator",
    "parameters": {},
    "priority": 5
  },
  ...
]

Zasady:
- priority: 1 (niski) do 10 (krytyczny) — nadaj wyższy priorytet zadaniom, od których zależą inne
- parameters: dodaj klucze specyficzne dla agenta, np. {"language": "python"} dla code_generator,
  {"mode": "commit", "branch": "bot/feature-x"} dla git
- Jeśli opis jest niejasny, stwórz jedno ogólne zadanie badawcze (researcher) na początku
- Maksymalnie 10 zadań z jednego pliku MD
"""


async def parse_md_to_tasks(
    client: AsyncOpenAI,
    md_content: str,
    model: str,
    excluded: set[AgentType],
    only: set[AgentType] | None,
) -> list[Task]:
    """Wysyła plik MD do OpenAI, otrzymuje listę zadań w JSON."""
    logger.info("Parsowanie pliku MD na zadania przez OpenAI…")

    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": MD_PARSER_PROMPT},
            {"role": "user", "content": f"Plik Markdown do sparsowania:\n\n{md_content}"},
        ],
        temperature=0.2,
        max_tokens=2048,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content or "{}"

    # OpenAI z json_object może zwrócić {"tasks": [...]} lub bezpośrednio [...]
    parsed = json.loads(raw)
    task_list = parsed if isinstance(parsed, list) else parsed.get("tasks", list(parsed.values())[0] if parsed else [])

    tasks: list[Task] = []
    for i, item in enumerate(task_list):
        try:
            agent_type = AgentType(item.get("agent_type", "researcher"))
        except ValueError:
            agent_type = AgentType.RESEARCHER

        # Filtrowanie
        if agent_type in excluded:
            logger.info(f"Pominięto zadanie '{item.get('name')}' (agent {agent_type.value} wykluczony)")
            continue
        if only and agent_type not in only:
            logger.info(f"Pominięto zadanie '{item.get('name')}' (tylko: {[a.value for a in only]})")
            continue

        tasks.append(Task(
            id=item.get("id", f"task_{i+1:03d}"),
            name=item.get("name", f"Zadanie {i+1}"),
            description=item.get("description", ""),
            agent_type=agent_type,
            parameters=item.get("parameters", {}),
            priority=item.get("priority", 5),
        ))

    logger.info(f"Wyodrębniono {len(tasks)} zadań (po filtracji).")
    return tasks


def build_orchestrator(excluded: set[AgentType], only: set[AgentType] | None) -> OrchestratorAgent:
    """Tworzy orkiestrator i rejestruje agentów (z pominięciem wykluczonych)."""
    orch_config = AgentConfig(
        name="Master Orchestrator",
        agent_type=AgentType.ORCHESTRATOR,
        description="Koordynuje wszystkich agentów na podstawie pliku MD",
        system_prompt=ORCHESTRATOR_PROMPT,
    )
    orchestrator = OrchestratorAgent(orch_config)

    for agent_type, (agent_cls, prompt, name) in AGENT_REGISTRY.items():
        if agent_type in excluded:
            logger.info(f"Agent {name} pominięty (--exclude)")
            continue
        if only and agent_type not in only:
            logger.info(f"Agent {name} pominięty (--only)")
            continue

        config = AgentConfig(
            name=name,
            agent_type=agent_type,
            description=f"Wyspecjalizowany agent: {name}",
            system_prompt=prompt,
        )
        orchestrator.register_agent(agent_type, agent_cls(config))

    return orchestrator


async def run(
    md_path: Path,
    excluded: set[AgentType],
    only: set[AgentType] | None,
    model: str,
    dry_run: bool,
) -> None:
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        logger.error("OPENAI_API_KEY nie jest ustawiony. Dodaj go do pliku .env.")
        sys.exit(1)

    md_content = md_path.read_text(encoding="utf-8")
    logger.info(f"Wczytano plik: {md_path} ({len(md_content)} znaków)")

    client = AsyncOpenAI(api_key=api_key)

    # 1. Parsowanie MD → zadania
    tasks = await parse_md_to_tasks(client, md_content, model, excluded, only)

    if not tasks:
        logger.warning("Brak zadań po filtracji. Zakończono bez uruchomienia agentów.")
        return

    # 2. Podgląd zadań
    logger.info("=" * 55)
    logger.info("Zadania do wykonania:")
    for t in sorted(tasks, key=lambda x: -x.priority):
        logger.info(f"  [{t.priority:2d}] {t.agent_type.value:16s} | {t.name}")
    logger.info("=" * 55)

    if dry_run:
        logger.info("Tryb --dry-run: zadania wyświetlone, agenci nie uruchomieni.")
        return

    # 3. Budowanie orkiestratora
    orchestrator = build_orchestrator(excluded, only)

    # 4. Przesyłanie zadań
    for task in tasks:
        await orchestrator.submit_task(task)

    # 5. Wykonanie wszystkich zadań
    orchestration_task = Task(
        id="orchestration_main",
        name="Wykonaj wszystkie zadania z pliku MD",
        description=f"Źródło: {md_path.name}",
        agent_type=AgentType.ORCHESTRATOR,
        priority=1,
    )
    response = await orchestrator.execute(orchestration_task)

    # 6. Raport
    logger.info("=" * 55)
    logger.info("Wyniki:")
    logger.info(f"  Sukces: {response.success}")
    if response.result:
        r = response.result
        logger.info(f"  Zadań łącznie:  {r.get('total_tasks', '?')}")
        logger.info(f"  Zakończonych:   {r.get('successful', '?')}")
        logger.info(f"  Nieudanych:     {r.get('failed', '?')}")
    if response.error:
        logger.error(f"  Błąd: {response.error}")
    logger.info("=" * 55)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_agent_list(value: str) -> set[AgentType]:
    """Parsuje 'researcher,analyst' → {AgentType.RESEARCHER, AgentType.ANALYST}."""
    result: set[AgentType] = set()
    for name in value.split(","):
        name = name.strip().lower()
        try:
            result.add(AgentType(name))
        except ValueError:
            valid = ", ".join(a.value for a in AgentType if a != AgentType.ORCHESTRATOR)
            print(f"Nieznany typ agenta: '{name}'. Dostępne: {valid}", file=sys.stderr)
            sys.exit(1)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Uruchamia orkiestrator na podstawie pliku Markdown opisującego projekt.\n"
            "Runs the orchestrator based on a Markdown file describing the project."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "plan",
        metavar="PLAN.md",
        help="Ścieżka do pliku Markdown z opisem projektu",
    )
    parser.add_argument(
        "--exclude",
        metavar="AGENT[,AGENT]",
        default="",
        help="Wyklucz agentów (np. --exclude researcher,analyst)",
    )
    parser.add_argument(
        "--only",
        metavar="AGENT[,AGENT]",
        default="",
        help="Używaj tylko tych agentów (np. --only code_generator,git)",
    )
    parser.add_argument(
        "--model",
        default="gpt-4o",
        metavar="MODEL",
        help="Model OpenAI do parsowania MD i wykonania (domyślnie: gpt-4o)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Tylko wyświetl wyodrębnione zadania, nie uruchamiaj agentów",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    plan_path = Path(args.plan)
    if not plan_path.exists():
        print(f"Plik nie istnieje: {plan_path}", file=sys.stderr)
        sys.exit(1)

    excluded = _parse_agent_list(args.exclude) if args.exclude else set()
    only = _parse_agent_list(args.only) if args.only else None

    asyncio.run(run(plan_path, excluded, only, args.model, args.dry_run))
