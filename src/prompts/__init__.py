"""Agent system prompts."""
from .orchestrator import SYSTEM_PROMPT as ORCHESTRATOR_PROMPT
from .code_generator import SYSTEM_PROMPT as CODE_GENERATOR_PROMPT
from .researcher import SYSTEM_PROMPT as RESEARCHER_PROMPT
from .task_executor import SYSTEM_PROMPT as TASK_EXECUTOR_PROMPT
from .analyst import SYSTEM_PROMPT as ANALYST_PROMPT
from .git_agent import SYSTEM_PROMPT as GIT_AGENT_PROMPT

__all__ = [
    "ORCHESTRATOR_PROMPT",
    "CODE_GENERATOR_PROMPT",
    "RESEARCHER_PROMPT",
    "TASK_EXECUTOR_PROMPT",
    "ANALYST_PROMPT",
    "GIT_AGENT_PROMPT",
]
