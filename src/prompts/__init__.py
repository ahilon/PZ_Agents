"""Agent system prompts."""
from .analyst import SYSTEM_PROMPT as ANALYST_PROMPT
from .code_generator import SYSTEM_PROMPT as CODE_GENERATOR_PROMPT
from .git_agent import SYSTEM_PROMPT as GIT_AGENT_PROMPT
from .orchestrator import SYSTEM_PROMPT as ORCHESTRATOR_PROMPT
from .project_init import SYSTEM_PROMPT as PROJECT_INIT_PROMPT
from .researcher import SYSTEM_PROMPT as RESEARCHER_PROMPT
from .skill_agent import SYSTEM_PROMPT as SKILL_AGENT_PROMPT
from .task_executor import SYSTEM_PROMPT as TASK_EXECUTOR_PROMPT

__all__ = [
    "ORCHESTRATOR_PROMPT",
    "CODE_GENERATOR_PROMPT",
    "RESEARCHER_PROMPT",
    "TASK_EXECUTOR_PROMPT",
    "ANALYST_PROMPT",
    "GIT_AGENT_PROMPT",
    "PROJECT_INIT_PROMPT",
    "SKILL_AGENT_PROMPT",
]
