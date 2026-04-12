"""Orchestrator agent for managing and coordinating other agents"""
import asyncio
import logging
from typing import Any, Dict, List

from src.models.agent import (
    AgentConfig, AgentResponse, Task, AgentType, AgentState
)
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class OrchestratorAgent(BaseAgent):
    """
    Orchestrator agent that manages and coordinates other agents.

    Responsible for:
    - Task distribution to specialized agents
    - Task scheduling and prioritization
    - Result aggregation
    - Error handling and retry logic
    """

    def __init__(self, config: AgentConfig):
        """Initialize orchestrator agent"""
        super().__init__(config)
        self.agents: Dict[AgentType, BaseAgent] = {}
        self.task_queue: List[Task] = []
        self.completed_tasks: Dict[str, AgentResponse] = {}
        self.failed_tasks: Dict[str, str] = {}

    def register_agent(self, agent_type: AgentType, agent: BaseAgent) -> None:
        """
        Register a specialized agent

        Args:
            agent_type: Type of agent
            agent: Agent instance
        """
        self.agents[agent_type] = agent
        logger.info(f"Registered {agent_type.value} agent: {agent.config.name}")

    def unregister_agent(self, agent_type: AgentType) -> None:
        """Unregister an agent by type"""
        agent = self.agents.pop(agent_type, None)
        if agent:
            logger.info(f"Unregistered agent: {agent.config.name}")

    async def submit_task(self, task: Task) -> str:
        """
        Submit a task for execution

        Args:
            task: Task to execute

        Returns:
            Task ID
        """
        self.task_queue.append(task)
        self.task_queue.sort(key=lambda t: -t.priority)
        logger.info(f"Task submitted: {task.name} (Priority: {task.priority})")
        return task.id

    async def _process_task(self, orchestration_task: Task) -> Any:
        """
        Process orchestration tasks — runs all queued tasks in parallel.

        Args:
            orchestration_task: Orchestration task

        Returns:
            Orchestration results
        """
        tasks_to_run = list(self.task_queue)
        self.task_queue.clear()

        results: List[AgentResponse] = await asyncio.gather(
            *[self._delegate_task(task) for task in tasks_to_run]
        )

        successful = 0
        failed = 0
        for task, result in zip(tasks_to_run, results):
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
        """
        Delegate a task to appropriate agent

        Args:
            task: Task to delegate

        Returns:
            Agent response
        """
        target_agent = self.agents.get(task.agent_type)

        if not target_agent:
            logger.error(f"No agent found for task type: {task.agent_type}")
            return AgentResponse(
                success=False,
                error=f"No agent available for type: {task.agent_type}",
                metadata={"task_id": task.id}
            )

        logger.info(f"Delegating task {task.name} to {target_agent.config.name}")
        return await target_agent.execute(task)

    async def get_orchestration_status(self) -> Dict[str, Any]:
        """Get orchestration status"""
        status = await self.get_status()
        status.update({
            "registered_agents": len(self.agents),
            "queued_tasks": len(self.task_queue),
            "completed_tasks": len(self.completed_tasks),
            "failed_tasks": len(self.failed_tasks),
            "agents": [
                {
                    "name": agent.config.name,
                    "type": agent.config.agent_type,
                    "state": agent.state
                }
                for agent in self.agents.values()
            ]
        })
        return status
