"""Testy jednostkowe dla BaseAgent."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from agents.base_agent import BaseAgent
from src.models.agent import AgentConfig, AgentResponse, AgentState, AgentType, Task


class ConcreteAgent(BaseAgent):
    """Minimalna implementacja do testów."""
    async def _process_task(self, task):
        return {"done": True}


@pytest_asyncio.fixture
async def agent():
    config = AgentConfig(
        name="Test Agent",
        agent_type=AgentType.CUSTOM,
        description="Test",
        model="some-model",
        system_prompt="some prompt",
        temperature=0.5,
        max_tokens=100,
    )
    return ConcreteAgent(config)


@pytest_asyncio.fixture
async def sample_task():
    return Task(
        id="task-id",
        name="Sample Task",
        description="A sample task for testing.",
        agent_type=AgentType.CUSTOM,
    )


class TestBaseAgentExecution:

    @pytest.mark.asyncio
    async def test_execute_success_returns_response(self, agent, sample_task):
        response = await agent.execute(sample_task)
        assert response.success is True
        assert response.result == {"done": True}

    @pytest.mark.asyncio
    async def test_execute_sets_state_idle_after_completion(self, agent, sample_task):
        await agent.execute(sample_task)
        assert agent.state == AgentState.IDLE

    @pytest.mark.asyncio
    async def test_execute_timeout_returns_error(self, agent, sample_task):
        with patch("agents.base_agent.asyncio.wait_for", side_effect=asyncio.TimeoutError):
            response = await agent.execute(sample_task)
        assert response.success is False
        assert "timeout" in response.error.lower()

    @pytest.mark.asyncio
    async def test_execute_exception_returns_error(self, agent, sample_task):
        agent._process_task = AsyncMock(side_effect=RuntimeError("boom"))
        response = await agent.execute(sample_task)
        assert response.success is False
        assert "boom" in response.error


class TestBaseAgentEdgeCases:

    @pytest.mark.asyncio
    async def test_execute_without_api_key_still_works(self, agent, sample_task):
        agent._llm = None
        response = await agent.execute(sample_task)
        assert response.success is True

    @pytest.mark.asyncio
    async def test_call_llm_without_client_returns_empty(self, agent):
        agent._llm = None
        result = await agent._call_llm("test", response_json=False)
        assert result == ""

    @pytest.mark.asyncio
    async def test_call_llm_with_client_returns_response(self, agent):
        mock_llm = MagicMock()
        mock_llm.chat.completions.create = AsyncMock(
            return_value=MagicMock(choices=[MagicMock(message=MagicMock(content="response"))])
        )
        agent._llm = mock_llm
        result = await agent._call_llm("test", response_json=False)
        assert result == "response"

    @pytest.mark.asyncio
    async def test_get_status_returns_correct_info(self, agent):
        status = await agent.get_status()
        assert status["id"] == agent.id
        assert status["name"] == agent.config.name
        assert status["type"] == agent.config.agent_type
        assert status["state"] == AgentState.IDLE
