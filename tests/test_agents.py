"""Unit tests for agents"""
import pytest
import pytest_asyncio
from src.models.agent import AgentConfig, AgentType, Task, AgentState
from src.agents.orchestrator_agent import OrchestratorAgent


@pytest_asyncio.fixture
async def orchestrator():
    """Create an orchestrator agent for testing"""
    config = AgentConfig(
        name="Test Orchestrator",
        agent_type=AgentType.ORCHESTRATOR,
        description="Test agent"
    )
    return OrchestratorAgent(config)


@pytest.mark.asyncio
async def test_orchestrator_creation(orchestrator):
    """Test orchestrator agent creation"""
    assert orchestrator is not None
    assert orchestrator.config.agent_type == AgentType.ORCHESTRATOR
    assert orchestrator.state == AgentState.IDLE


@pytest.mark.asyncio
async def test_task_submission(orchestrator):
    """Test task submission"""
    task = Task(
        id="test_001",
        name="Test Task",
        description="A test task",
        agent_type=AgentType.CODE_GENERATOR,
        priority=5
    )
    
    task_id = await orchestrator.submit_task(task)
    assert task_id == "test_001"
    assert len(orchestrator.task_queue) > 0


@pytest.mark.asyncio
async def test_orchestrator_status(orchestrator):
    """Test getting orchestrator status"""
    status = await orchestrator.get_orchestration_status()
    
    assert "id" in status
    assert "name" in status
    assert "registered_agents" in status
    assert status["state"] == AgentState.IDLE
