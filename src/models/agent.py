"""Agent models and base classes"""
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AgentType(str, Enum):
    """Types of agents in the system"""
    ORCHESTRATOR = "orchestrator"
    CODE_GENERATOR = "code_generator"
    TASK_EXECUTOR = "task_executor"
    RESEARCHER = "researcher"
    ANALYST = "analyst"
    GIT = "git"
    PROJECT_INIT = "project_init"
    SKILL = "skill"
    UI = "ui"
    VISION = "vision"
    FILE_PROCESSOR = "file_processor"
    DOCX = "docx"
    TRIP_PLANNER = "trip_planner"
    CUSTOM = "custom"


class AgentState(str, Enum):
    """Agent execution states"""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    WAITING = "waiting"


class TaskStatus(str, Enum):
    """Task lifecycle statuses"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Task(BaseModel):
    """Task model"""
    id: str = Field(..., description="Unique task identifier")
    name: str = Field(..., description="Task name")
    description: str = Field(..., description="Task description")
    agent_type: AgentType = Field(..., description="Target agent type")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Task parameters")
    priority: int = Field(default=1, ge=1, le=10, description="Task priority (1-10)")
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="Task status")


class AgentConfig(BaseModel):
    """Agent configuration"""
    name: str = Field(..., description="Agent name")
    agent_type: AgentType = Field(..., description="Agent type")
    description: str = Field(..., description="Agent description")
    model: str = Field(default="gpt-4o", description="LLM model to use")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Model temperature")
    max_tokens: int = Field(default=2000, ge=100, description="Maximum tokens")
    system_prompt: Optional[str] = Field(default=None, description="System prompt for the agent")
    tools: List[str] = Field(default_factory=list, description="Available tools")


class AgentResponse(BaseModel):
    """Agent response model"""
    success: bool = Field(..., description="Whether task succeeded")
    result: Optional[Any] = Field(default=None, description="Task result")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
