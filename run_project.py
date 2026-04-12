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

from agents.git_agent import SYSTEM_PROMPT as GIT_AGENT_PROMPT
from agents.git_agent import GitAgent
from agents.orchestrator_agent import SYSTEM_PROMPT as ORCHESTRATOR_PROMPT
from agents.orchestrator_agent import OrchestratorAgent
from agents.project_init_agent import SYSTEM_PROMPT as PROJECT_INIT_PROMPT
from agents.project_init_agent import ProjectInitAgent
from agents.skill_agent import SYSTEM_PROMPT as SKILL_AGENT_PROMPT
from agents.skill_agent import SkillAgent
from agents.specialized_agents import (
    ANALYST_PROMPT,
    CODE_GENERATOR_PROMPT,
    RESEARCHER_PROMPT,
    TASK_EXECUTOR_PROMPT,
    AnalystAgent,
    CodeGeneratorAgent,
    ResearcherAgent,
    TaskExecutorAgent,
)
from agents.ui_agent import SYSTEM_PROMPT as UI_AGENT_PROMPT
from agents.ui_agent import UIAgent
from src.config.settings import settings
from src.models.agent import AgentConfig, AgentType, Task

load_dotenv()

logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Mapowanie nazwy → klasa agenta, prompt, wyświetlana nazwa
AGENT_REGISTRY: dict[AgentType, tuple[type, str, str]] = {
    AgentType.CODE_GENERATOR: (CodeGeneratorAgent, CODE_GENERATOR_PROMPT, "Code Generator"),
    AgentType.RESEARCHER:     (ResearcherAgent,     RESEARCHER_PROMPT,     "Researcher"),
    AgentType.TASK_EXECUTOR:  (TaskExecutorAgent,   TASK_EXECUTOR_PROMPT,  "Task Executor"),
    AgentType.ANALYST:        (AnalystAgent,        ANALYST_PROMPT,        "Analyst"),
    AgentType.GIT:            (GitAgent,            GIT_AGENT_PROMPT,      "Git Agent"),
    AgentType.PROJECT_INIT:   (ProjectInitAgent,    PROJECT_INIT_PROMPT,   "Project Init Agent"),
    AgentType.SKILL:          (SkillAgent,          SKILL_AGENT_PROMPT,    "Skill Agent"),
    AgentType.UI:             (UIAgent,             UI_AGENT_PROMPT,       "UI Agent"),
}

# Prompt parsujący plik MD → lista zadań
MD_PARSER_PROMPT = """Jesteś asystentem parsującym opisy projektów.
Otrzymasz plik Markdown opisujący projekt lub zadania do wykonania.
Wyodrębnij z niego listę zadań i zwróć JSON w formacie:
{
  "tasks": [
    {
      "id": "task_001",
      "name": "Nazwa zadania",
      "description": "Opis co zrobić",
      "agent_type": "code_generator|researcher|task_executor|analyst|git|project_init|skill|ui",
      "parameters": {},
      "priority": 5
    }
  ]
}
Dozwolone wartości agent_type: code_generator, researcher, task_executor, analyst, git, project_init, skill, ui.
Jeśli nie możesz jednoznacznie przypisać agenta — użyj researcher.
Zwróć TYLKO JSON, bez żadnego dodatkowego tekstu.
"""


async def parse_md_to_tasks(
    md_content: str,
    model: str,
    api_key: str,
    excluded: set[AgentType],
    only: set[AgentType] | None,
) -> list[Task]:
    client = AsyncOpenAI(api_key=api_key)
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": MD_PARSER_PROMPT},
            {"role": "user",   "content": md_content},
        ],
        temperature=0.2,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content or "{}"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.error(f"Błąd parsowania JSON: {raw[:200]}")
        return []

    tasks: list[Task] = []
    for item in data.get("tasks", []):
        try:
            agent_type = AgentType(item.get("agent_type", "researcher"))
        except ValueError:
            agent_type = AgentType.RESEARCHER

        if agent_type in excluded:
            logger.info(f"Pomijam zadanie '{item.get('name')}' (wyłączony agent: {agent_type.value})")
            continue
        if only and agent_type not in only:
            logger.info(f"Pomijam zadanie '{item.get('name')}' (agent {agent_type.value} nie na liście --only)")
            continue

        tasks.append(Task(
            id=item.get("id", f"task_{len(tasks):03d}"),
            name=item.get("name", "Zadanie"),
            description=item.get("description", ""),
            agent_type=agent_type,
            parameters=item.get("parameters", {}),
            priority=item.get("priority", 5),
        ))

    return tasks


def build_orchestrator(excluded: set[AgentType], only: set[AgentType] | None) -> OrchestratorAgent:
    orchestrator = OrchestratorAgent(AgentConfig(
        name="Orchestrator",
        agent_type=AgentType.ORCHESTRATOR,
        description="Koordynuje agenty na podstawie pliku projektu",
        system_prompt=ORCHESTRATOR_PROMPT,
    ))

    for agent_type, (agent_cls, prompt, name) in AGENT_REGISTRY.items():
        if agent_type in excluded:
            continue
        if only and agent_type not in only:
            continue
        agent = agent_cls(AgentConfig(
            name=name, agent_type=agent_type,
            description=f"Agent typu {agent_type.value}",
            system_prompt=prompt,
        ))
        orchestrator.register_agent(agent_type, agent)
        logger.info(f"Zarejestrowano agenta: {name}")

    return orchestrator


async def run_project(
    md_path: Path,
    model: str,
    excluded: set[AgentType],
    only: set[AgentType] | None,
    dry_run: bool,
) -> None:
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        logger.error("OPENAI_API_KEY nie ustawiony.")
        sys.exit(1)

    md_content = md_path.read_text(encoding="utf-8")
    logger.info(f"Wczytano plik: {md_path} ({len(md_content)} znaków)")

    logger.info("Parsuję zadania z pliku Markdown...")
    tasks = await parse_md_to_tasks(md_content, model, api_key, excluded, only)

    if not tasks:
        logger.warning("Nie znaleziono żadnych zadań.")
        return

    logger.info(f"Znaleziono {len(tasks)} zadań:")
    for task in tasks:
        logger.info(f"  [{task.agent_type.value}] {task.name} (priorytet: {task.priority})")

    if dry_run:
        logger.info("Tryb --dry-run: nie wykonuję zadań.")
        return

    orchestrator = build_orchestrator(excluded, only)
    for task in tasks:
        await orchestrator.submit_task(task)

    orchestration_task = Task(
        id="orchestration_main",
        name="Wykonaj wszystkie zadania z pliku projektu",
        description=f"Plik źródłowy: {md_path.name}",
        agent_type=AgentType.ORCHESTRATOR,
        priority=5,
    )

    logger.info("Uruchamiam orchestrator...")
    response = await orchestrator.execute(orchestration_task)

    if response.success and response.result:
        r = response.result
        logger.info(f"Zakończono: {r.get('successful', 0)}/{r.get('total_tasks', 0)} sukcesów")
    else:
        logger.error(f"Orchestrator nieudany: {response.error}")


def _parse_agent_list(value: str) -> set[AgentType]:
    result: set[AgentType] = set()
    for name in value.split(","):
        name = name.strip()
        if not name:
            continue
        try:
            result.add(AgentType(name))
        except ValueError:
            valid = ", ".join(a.value for a in AgentType if a != AgentType.ORCHESTRATOR)
            logger.error(f"Nieznany typ agenta: '{name}'. Dostępne: {valid}")
            sys.exit(1)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Uruchamia system agentów na podstawie pliku Markdown.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("md_file", help="Ścieżka do pliku Markdown opisującego projekt")
    parser.add_argument("--model", default="gpt-4o", help="Model OpenAI (domyślnie: gpt-4o)")
    parser.add_argument("--exclude", default="", help="Agenty do pominięcia, np. researcher,analyst")
    parser.add_argument("--only", default="", help="Uruchom tylko te agenty, np. code_generator,git")
    parser.add_argument("--dry-run", action="store_true", help="Parsuj zadania, ale nie wykonuj")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    md_path = Path(args.md_file)
    if not md_path.exists():
        print(f"Błąd: plik '{md_path}' nie istnieje.")
        sys.exit(1)

    excluded = _parse_agent_list(args.exclude)
    only     = _parse_agent_list(args.only) or None

    asyncio.run(run_project(md_path, args.model, excluded, only, args.dry_run))
