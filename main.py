"""Main entry point and example usage."""
import asyncio
import logging
from typing import List

from agents.orchestrator_agent import SYSTEM_PROMPT as ORCHESTRATOR_PROMPT
from agents.orchestrator_agent import OrchestratorAgent
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
from src.config.settings import settings
from src.models.agent import AgentConfig, AgentType, Task

logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def initialize_agents() -> OrchestratorAgent:
    orchestrator = OrchestratorAgent(AgentConfig(
        name="Master Orchestrator",
        agent_type=AgentType.ORCHESTRATOR,
        description="Coordinates all other agents",
        system_prompt=ORCHESTRATOR_PROMPT,
    ))

    for cls, prompt, name, desc, atype in [
        (CodeGeneratorAgent, CODE_GENERATOR_PROMPT, "Code Generator", "Generates code", AgentType.CODE_GENERATOR),
        (ResearcherAgent,    RESEARCHER_PROMPT,    "Researcher",     "Researches info", AgentType.RESEARCHER),
        (TaskExecutorAgent,  TASK_EXECUTOR_PROMPT, "Task Executor",  "Executes tasks",  AgentType.TASK_EXECUTOR),
        (AnalystAgent,       ANALYST_PROMPT,       "Data Analyst",   "Analyzes data",   AgentType.ANALYST),
    ]:
        agent = cls(AgentConfig(name=name, agent_type=atype, description=desc, system_prompt=prompt))
        orchestrator.register_agent(atype, agent)

    return orchestrator


async def create_sample_tasks() -> List[Task]:
    return [
        Task(id="task_001", name="Generate REST API",
             description="Generate a Python REST API with FastAPI",
             agent_type=AgentType.CODE_GENERATOR,
             parameters={"language": "python", "framework": "fastapi"}, priority=10),
        Task(id="task_002", name="Research Python Best Practices",
             description="Research and compile Python best practices",
             agent_type=AgentType.RESEARCHER,
             parameters={"topic": "python best practices"}, priority=8),
        Task(id="task_003", name="Analyze Project Metrics",
             description="Analyze project performance metrics",
             agent_type=AgentType.ANALYST,
             parameters={"metrics": ["performance", "code_quality"]}, priority=5),
    ]


async def main() -> None:
    logger.info("=" * 50)
    logger.info("Starting AI Agents System")
    logger.info("=" * 50)

    try:
        orchestrator = await initialize_agents()
        status = await orchestrator.get_orchestration_status()
        logger.info(f"Orchestrator Status: {status}")

        tasks = await create_sample_tasks()
        for task in tasks:
            task_id = await orchestrator.submit_task(task)
            logger.info(f"Task submitted — ID: {task_id}, Name: {task.name}")

        orchestration_task = Task(
            id="orchestration_001", name="Execute All Tasks",
            description="Execute all submitted tasks",
            agent_type=AgentType.ORCHESTRATOR, priority=5,
        )
        response = await orchestrator.execute(orchestration_task)
        logger.info(f"Success: {response.success}")
        logger.info(f"Result: {response.result}")

        final_status = await orchestrator.get_orchestration_status()
        logger.info(f"Completed Tasks: {final_status['completed_tasks']}")
        logger.info(f"Failed Tasks: {final_status['failed_tasks']}")

    except Exception as e:
        logger.error(f"Error during execution: {e}", exc_info=True)

    logger.info("=" * 50)
    logger.info("AI Agents System Finished")
    logger.info("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
