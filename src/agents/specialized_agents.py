"""Implementacje wyspecjalizowanych agentów."""
import json
import logging
from typing import Any

from src.models.agent import Task
from src.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


def _build_user_message(task: Task) -> str:
    """Buduje wiadomość użytkownika z zadania."""
    parts = [f"Zadanie: {task.name}", f"Opis: {task.description}"]
    if task.parameters:
        parts.append(f"Parametry: {json.dumps(task.parameters, ensure_ascii=False, indent=2)}")
    return "\n".join(parts)


def _parse_json_result(raw: str, fallback_key: str = "result") -> Any:
    """Parsuje JSON z odpowiedzi LLM, z fallbackiem."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {fallback_key: raw, "status": "completed"}


class CodeGeneratorAgent(BaseAgent):
    """Agent generujący kod na podstawie opisu zadania."""

    async def _process_task(self, task: Task) -> Any:
        logger.info(f"CodeGenerator: generuję kod dla: {task.name}")
        raw = await self._call_llm(_build_user_message(task), response_json=True)
        result = _parse_json_result(raw)
        result.setdefault("status", "generated")
        result.setdefault("language", task.parameters.get("language", "python"))
        return result


class ResearcherAgent(BaseAgent):
    """Agent zbierający i syntezujący informacje."""

    async def _process_task(self, task: Task) -> Any:
        logger.info(f"Researcher: badam: {task.name}")
        raw = await self._call_llm(_build_user_message(task), response_json=True)
        result = _parse_json_result(raw)
        result.setdefault("status", "completed")
        result.setdefault("topic", task.name)
        return result


class TaskExecutorAgent(BaseAgent):
    """Agent wykonujący zadania systemowe i procedury."""

    async def _process_task(self, task: Task) -> Any:
        logger.info(f"TaskExecutor: wykonuję: {task.name}")
        raw = await self._call_llm(_build_user_message(task), response_json=True)
        result = _parse_json_result(raw)
        result.setdefault("status", "completed")
        result.setdefault("executed", True)
        return result


class AnalystAgent(BaseAgent):
    """Agent analizujący dane i generujący wnioski."""

    async def _process_task(self, task: Task) -> Any:
        logger.info(f"Analyst: analizuję: {task.name}")
        raw = await self._call_llm(_build_user_message(task), response_json=True)
        result = _parse_json_result(raw)
        result.setdefault("status", "completed")
        result.setdefault("subject", task.name)
        return result
