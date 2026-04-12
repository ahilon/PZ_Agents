"""Unit tests for agents."""
import pytest
import pytest_asyncio

from agents.orchestrator_agent import OrchestratorAgent
from src.models.agent import AgentConfig, AgentState, AgentType, Task


@pytest_asyncio.fixture
async def orchestrator():
    config = AgentConfig(
        name="Test Orchestrator",
        agent_type=AgentType.ORCHESTRATOR,
        description="Test agent",
    )
    return OrchestratorAgent(config)


@pytest.mark.asyncio
async def test_orchestrator_creation(orchestrator):
    assert orchestrator is not None
    assert orchestrator.config.agent_type == AgentType.ORCHESTRATOR
    assert orchestrator.state == AgentState.IDLE


@pytest.mark.asyncio
async def test_task_submission(orchestrator):
    task = Task(
        id="test_001",
        name="Test Task",
        description="A test task",
        agent_type=AgentType.CODE_GENERATOR,
        priority=5,
    )
    task_id = await orchestrator.submit_task(task)
    assert task_id == "test_001"
    assert len(orchestrator.task_queue) > 0


@pytest.mark.asyncio
async def test_orchestrator_status(orchestrator):
    status = await orchestrator.get_orchestration_status()
    assert "id" in status
    assert "name" in status
    assert "registered_agents" in status
    assert status["state"] == AgentState.IDLE
