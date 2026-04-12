"""Base agent class"""
import asyncio
import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, Optional
import uuid

from dotenv import load_dotenv
from openai import AsyncOpenAI

from src.models.agent import AgentConfig, AgentResponse, Task, AgentState

load_dotenv()

logger = logging.getLogger(__name__)

DEFAULT_TASK_TIMEOUT = float(os.getenv("AGENT_TIMEOUT_SECONDS", "120"))


class BaseAgent(ABC):
    """Klasa bazowa dla wszystkich agentów."""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.id = str(uuid.uuid4())
        self.state = AgentState.IDLE
        self.created_at = datetime.now()
        self.last_activity = datetime.now()

        api_key = os.getenv("OPENAI_API_KEY", "")
        self._llm: Optional[AsyncOpenAI] = AsyncOpenAI(api_key=api_key) if api_key else None

        logger.info(f"Zainicjalizowano agenta {self.config.name} (ID: {self.id})")

    async def execute(self, task: Task) -> AgentResponse:
        """Wykonuje zadanie z timeoutem."""
        self.state = AgentState.RUNNING
        self.last_activity = datetime.now()
        started_at = datetime.now()

        logger.info(f"Agent {self.config.name} wykonuje zadanie: {task.name}")

        try:
            result = await asyncio.wait_for(
                self._process_task(task),
                timeout=DEFAULT_TASK_TIMEOUT,
            )
            self.state = AgentState.IDLE

            return AgentResponse(
                success=True,
                result=result,
                metadata={
                    "agent_id": self.id,
                    "agent_name": self.config.name,
                    "task_id": task.id,
                    "execution_time": (datetime.now() - started_at).total_seconds(),
                },
            )

        except asyncio.TimeoutError:
            self.state = AgentState.IDLE
            msg = f"Zadanie przekroczyło timeout ({DEFAULT_TASK_TIMEOUT}s)"
            logger.error(f"Agent {self.config.name}: {msg}")
            return AgentResponse(
                success=False,
                error=msg,
                metadata={"agent_id": self.id, "agent_name": self.config.name, "task_id": task.id},
            )

        except Exception as e:
            self.state = AgentState.IDLE
            logger.error(f"Agent {self.config.name} błąd: {e}", exc_info=True)
            return AgentResponse(
                success=False,
                error=str(e),
                metadata={"agent_id": self.id, "agent_name": self.config.name, "task_id": task.id},
            )

    async def _call_llm(self, user_message: str, response_json: bool = True) -> str:
        """Wywołuje OpenAI z system promptem agenta. Zwraca string (JSON lub tekst)."""
        if not self._llm:
            logger.warning(f"Agent {self.config.name}: brak OPENAI_API_KEY, pomijam wywołanie LLM.")
            return "{}" if response_json else ""

        kwargs: Dict[str, Any] = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": self.config.system_prompt or ""},
                {"role": "user",   "content": user_message},
            ],
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        if response_json:
            kwargs["response_format"] = {"type": "json_object"}

        response = await self._llm.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ("{}" if response_json else "")

    @abstractmethod
    async def _process_task(self, task: Task) -> Any:
        """Logika agenta — implementowana przez podklasy."""
        pass

    async def get_status(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.config.name,
            "type": self.config.agent_type,
            "state": self.state,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
        }
