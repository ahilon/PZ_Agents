"""Orchestrator agent — koordynuje pozostałe agenty."""
import asyncio
import logging
from typing import Any, Dict, List

from agents.base_agent import BaseAgent
from src.models.agent import AgentConfig, AgentResponse, AgentState, AgentType, Task

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Jesteś Głównym Orkiestratorem — centralnym koordynatorem systemu wieloagentowego.

## Twoja rola
Otrzymujesz cel wysokiego poziomu od użytkownika, rozkładasz go na konkretne zadania
i delegujesz je do odpowiednich wyspecjalizowanych agentów:
- CODE_GENERATOR  → pisanie, refaktoryzacja lub przegląd kodu
- RESEARCHER      → zbieranie faktów, dokumentacji lub informacji zewnętrznych
- TASK_EXECUTOR   → uruchamianie poleceń, skryptów lub wieloetapowych procedur
- ANALYST         → interpretacja danych, metryk lub wyników

## Jak działasz
1. **Dekompozycja** — podziel cel użytkownika na jak najmniejsze, niezależne podzadania.
2. **Priorytetyzacja** — przypisz każdemu zadaniu priorytet (1 = niski … 10 = krytyczny).
3. **Delegowanie** — skieruj każde zadanie do dokładnie jednego typu agenta.
4. **Monitorowanie** — śledź, które zadania się powiodły, a które nie.
5. **Agregacja** — zbierz wszystkie odpowiedzi i przygotuj spójną odpowiedź końcową.

## Zasady
- Nigdy nie wykonuj pracy domenowej samodzielnie — zawsze deleguj.
- Jeśli agent zawiedzie, spróbuj ponownie lub oznacz zadanie jako nieudane.
- Gdy wiele zadań może być wykonanych równolegle, wyślij je wszystkie jednocześnie.
- Zawsze raportuj: łączną liczbę zadań, zakończone sukcesem, zakończone niepowodzeniem.

## Format odpowiedzi końcowej
```
Status: OK | CZĘŚCIOWY | BŁĄD
Zadania: <łącznie> przesłanych, <n> zakończonych sukcesem, <n> zakończonych niepowodzeniem

Wyniki:
- [NAZWA ZADANIA] → <jednozdaniowe podsumowanie wyniku>

Podsumowanie:
<2–4 zdania syntetyzujące to, co zostało wykonane>
```
"""


class OrchestratorAgent(BaseAgent):
    """Koordynuje inne agenty — rozdziela zadania i agreguje wyniki."""

    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self.agents: Dict[AgentType, BaseAgent] = {}
        self.task_queue: List[Task] = []
        self.completed_tasks: Dict[str, AgentResponse] = {}
        self.failed_tasks: Dict[str, str] = {}

    def register_agent(self, agent_type: AgentType, agent: BaseAgent) -> None:
        self.agents[agent_type] = agent
        logger.info(f"Zarejestrowano agenta {agent_type.value}: {agent.config.name}")

    def unregister_agent(self, agent_type: AgentType) -> None:
        agent = self.agents.pop(agent_type, None)
        if agent:
            logger.info(f"Wyrejestrowano agenta: {agent.config.name}")

    async def submit_task(self, task: Task) -> str:
        self.task_queue.append(task)
        self.task_queue.sort(key=lambda t: -t.priority)
        logger.info(f"Zadanie dodane do kolejki: {task.name} (priorytet: {task.priority})")
        return task.id

    async def _process_task(self, orchestration_task: Task) -> Any:
        tasks_to_run = list(self.task_queue)
        self.task_queue.clear()

        results: List[AgentResponse] = await asyncio.gather(
            *[self._delegate_task(task) for task in tasks_to_run],
            return_exceptions=True,
        )

        successful = 0
        failed = 0
        for task, result in zip(tasks_to_run, results):
            if isinstance(result, Exception):
                result = AgentResponse(success=False, error=str(result),
                                       metadata={"task_id": task.id})
            if result.success:
                self.completed_tasks[task.id] = result
                successful += 1
            else:
                self.failed_tasks[task.id] = result.error or "Unknown error"
                failed += 1

        return {
            "total_tasks": len(results),
            "successful": successful,
            "failed": failed,
            "results": results,
        }

    async def _delegate_task(self, task: Task) -> AgentResponse:
        target_agent = self.agents.get(task.agent_type)
        if not target_agent:
            logger.error(f"Brak agenta dla typu: {task.agent_type}")
            return AgentResponse(
                success=False,
                error=f"Brak agenta dla typu: {task.agent_type}",
                metadata={"task_id": task.id},
            )
        logger.info(f"Deleguję zadanie '{task.name}' do {target_agent.config.name}")
        return await target_agent.execute(task)

    async def get_orchestration_status(self) -> Dict[str, Any]:
        status = await self.get_status()
        status.update({
            "registered_agents": len(self.agents),
            "queued_tasks": len(self.task_queue),
            "completed_tasks": len(self.completed_tasks),
            "failed_tasks": len(self.failed_tasks),
            "agents": [
                {"name": a.config.name, "type": a.config.agent_type, "state": a.state}
                for a in self.agents.values()
            ],
        })
        return status
