"""Base agent class"""
import logging
from typing import Any, Dict, Optional
from abc import ABC, abstractmethod
import uuid
from datetime import datetime

from src.models.agent import AgentConfig, AgentResponse, Task, AgentState

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Base class for all agents"""
    
    def __init__(self, config: AgentConfig):
        """
        Initialize the base agent
        
        Args:
            config: Agent configuration
        """
        self.config = config
        self.id = str(uuid.uuid4())
        self.state = AgentState.IDLE
        self.created_at = datetime.now()
        self.last_activity = datetime.now()
        
        logger.info(f"Initialized agent {self.config.name} (ID: {self.id})")
    
    async def execute(self, task: Task) -> AgentResponse:
        """
        Execute a task
        
        Args:
            task: Task to execute
            
        Returns:
            Agent response with result or error
        """
        try:
            self.state = AgentState.RUNNING
            self.last_activity = datetime.now()
            
            logger.info(f"Agent {self.config.name} executing task: {task.name}")
            
            # Call the abstract method implemented by subclasses
            result = await self._process_task(task)
            
            self.state = AgentState.IDLE

            return AgentResponse(
                success=True,
                result=result,
                metadata={
                    "agent_id": self.id,
                    "agent_name": self.config.name,
                    "task_id": task.id,
                    "execution_time": (datetime.now() - self.last_activity).total_seconds()
                }
            )

        except Exception as e:
            self.state = AgentState.IDLE
            logger.error(f"Agent {self.config.name} failed: {str(e)}")
            
            return AgentResponse(
                success=False,
                error=str(e),
                metadata={
                    "agent_id": self.id,
                    "agent_name": self.config.name,
                    "task_id": task.id
                }
            )
    
    @abstractmethod
    async def _process_task(self, task: Task) -> Any:
        """
        Process the task - to be implemented by subclasses
        
        Args:
            task: Task to process
            
        Returns:
            Task result
        """
        pass
    
    async def get_status(self) -> Dict[str, Any]:
        """Get agent status"""
        return {
            "id": self.id,
            "name": self.config.name,
            "type": self.config.agent_type,
            "state": self.state,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat()
        }
