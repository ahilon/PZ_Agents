"""Main entry point and example usage"""
import asyncio
import logging
from typing import List

from src.config.settings import settings
from src.models.agent import AgentConfig, AgentType, Task
from src.agents.orchestrator_agent import OrchestratorAgent
from src.agents.specialized_agents import (
    CodeGeneratorAgent,
    ResearcherAgent,
    TaskExecutorAgent,
    AnalystAgent
)
from src.prompts import (
    ORCHESTRATOR_PROMPT,
    CODE_GENERATOR_PROMPT,
    RESEARCHER_PROMPT,
    TASK_EXECUTOR_PROMPT,
    ANALYST_PROMPT,
)

# Configure logging
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def initialize_agents() -> OrchestratorAgent:
    """
    Initialize all agents
    
    Returns:
        OrchestratorAgent instance with registered agents
    """
    
    # Create orchestrator
    orchestrator_config = AgentConfig(
        name="Master Orchestrator",
        agent_type=AgentType.ORCHESTRATOR,
        description="Coordinates all other agents",
        system_prompt=ORCHESTRATOR_PROMPT,
    )
    orchestrator = OrchestratorAgent(orchestrator_config)
    
    # Create specialized agents
    code_gen_config = AgentConfig(
        name="Code Generator",
        agent_type=AgentType.CODE_GENERATOR,
        description="Generates code based on requirements",
        system_prompt=CODE_GENERATOR_PROMPT,
    )
    code_gen_agent = CodeGeneratorAgent(code_gen_config)
    orchestrator.register_agent(AgentType.CODE_GENERATOR, code_gen_agent)
    
    researcher_config = AgentConfig(
        name="Researcher",
        agent_type=AgentType.RESEARCHER,
        description="Researches and gathers information",
        system_prompt=RESEARCHER_PROMPT,
    )
    researcher_agent = ResearcherAgent(researcher_config)
    orchestrator.register_agent(AgentType.RESEARCHER, researcher_agent)
    
    executor_config = AgentConfig(
        name="Task Executor",
        agent_type=AgentType.TASK_EXECUTOR,
        description="Executes system tasks",
        system_prompt=TASK_EXECUTOR_PROMPT,
    )
    executor_agent = TaskExecutorAgent(executor_config)
    orchestrator.register_agent(AgentType.TASK_EXECUTOR, executor_agent)
    
    analyst_config = AgentConfig(
        name="Data Analyst",
        agent_type=AgentType.ANALYST,
        description="Analyzes data and provides insights",
        system_prompt=ANALYST_PROMPT,
    )
    analyst_agent = AnalystAgent(analyst_config)
    orchestrator.register_agent(AgentType.ANALYST, analyst_agent)
    
    return orchestrator


async def create_sample_tasks() -> List[Task]:
    """Create sample tasks for demonstration"""
    
    tasks = [
        Task(
            id="task_001",
            name="Generate REST API",
            description="Generate a Python REST API with FastAPI",
            agent_type=AgentType.CODE_GENERATOR,
            parameters={"language": "python", "framework": "fastapi"},
            priority=10
        ),
        Task(
            id="task_002",
            name="Research Python Best Practices",
            description="Research and compile Python best practices",
            agent_type=AgentType.RESEARCHER,
            parameters={"topic": "python best practices"},
            priority=8
        ),
        Task(
            id="task_003",
            name="Analyze Project Metrics",
            description="Analyze project performance metrics",
            agent_type=AgentType.ANALYST,
            parameters={"metrics": ["performance", "code_quality"]},
            priority=5
        ),
    ]
    
    return tasks


async def main():
    """Main execution function"""
    
    logger.info("=" * 50)
    logger.info("Starting AI Agents System")
    logger.info("=" * 50)
    
    try:
        # Initialize agents
        logger.info("Initializing agents...")
        orchestrator = await initialize_agents()
        
        # Get status
        status = await orchestrator.get_orchestration_status()
        logger.info(f"Orchestrator Status: {status}")
        
        # Create sample tasks
        logger.info("\nCreating sample tasks...")
        tasks = await create_sample_tasks()
        
        # Submit tasks
        logger.info("Submitting tasks...")
        for task in tasks:
            task_id = await orchestrator.submit_task(task)
            logger.info(f"Task submitted - ID: {task_id}, Name: {task.name}")
        
        # Execute orchestration
        logger.info("\nExecuting task orchestration...")
        orchestration_task = Task(
            id="orchestration_001",
            name="Execute All Tasks",
            description="Execute all submitted tasks",
            agent_type=AgentType.ORCHESTRATOR,
            priority=5
        )
        
        response = await orchestrator.execute(orchestration_task)
        
        logger.info("\n" + "=" * 50)
        logger.info("Execution Results:")
        logger.info("=" * 50)
        logger.info(f"Success: {response.success}")
        logger.info(f"Result: {response.result}")
        
        if response.metadata:
            logger.info(f"Metadata: {response.metadata}")
        
        # Final status
        logger.info("\nFinal Orchestrator Status:")
        final_status = await orchestrator.get_orchestration_status()
        logger.info(f"Completed Tasks: {final_status['completed_tasks']}")
        logger.info(f"Failed Tasks: {final_status['failed_tasks']}")
        
    except Exception as e:
        logger.error(f"Error during execution: {str(e)}", exc_info=True)
    
    logger.info("\n" + "=" * 50)
    logger.info("AI Agents System Finished")
    logger.info("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
