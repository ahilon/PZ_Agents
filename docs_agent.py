"""
Docs Agent — automatyczna aktualizacja README.md na podstawie zmian w kodzie.
Docs Agent — automatic README.md updates based on code changes.

Uruchomienie / Usage:
    poetry run python docs_agent.py                     # aktualizuj jeśli są zmiany git / update if git changes
    poetry run python docs_agent.py --initial           # wygeneruj kompletny README od zera / generate full README from scratch
    poetry run python docs_agent.py --since 10          # ostatnie 10 commitów / last 10 commits
    poetry run python docs_agent.py --output DOCS.md    # inny plik wyjściowy / different output file
    poetry run python docs_agent.py --force             # regeneruj bez względu na zmiany / force regenerate
"""

import argparse
import asyncio
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from openai import AsyncOpenAI

from src.prompts.docs_agent import SYSTEM_PROMPT as README_SYSTEM_PROMPT
from src.prompts.docs_agent import INITIAL_SYSTEM_PROMPT as INITIAL_README_SYSTEM_PROMPT

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent

# Pliki i katalogi pomijane przy skanowaniu / Files and dirs skipped during scan
IGNORE_PATTERNS = {
    ".venv", "venv", "__pycache__", ".git", ".pytest_cache",
    "node_modules", "dist", "build", ".mypy_cache", ".ruff_cache",
    "poetry.lock", ".DS_Store", "*.pyc",
}

# Pliki kluczowe do wczytania jako kontekst / Key files to read as context
CONTEXT_FILES = [
    "pyproject.toml",
    "src/models/agent.py",
    "src/agents/base_agent.py",
    "src/agents/orchestrator_agent.py",
    "src/agents/specialized_agents.py",
    "src/agents/git_agent.py",
    "src/config/settings.py",
    "src/prompts/__init__.py",
    "src/tools/file_tools.py",
    "src/tools/code_executor.py",
    "tests/test_agents.py",
    "main.py",
    "run_project.py",
]


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def _run_git(args: list[str]) -> str:
    """Run a git command and return stdout, empty string on failure."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=15,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""


def get_git_info(since_commits: int = 20) -> dict:
    """Collect git metadata about recent changes."""
    is_repo = bool(_run_git(["rev-parse", "--is-inside-work-tree"]))

    if not is_repo:
        return {"available": False, "reason": "not a git repository"}

    log = _run_git([
        "log", f"-{since_commits}", "--oneline", "--no-merges",
    ])
    diff_stat = _run_git([
        "diff", f"HEAD~{min(since_commits, 5)}..HEAD", "--stat",
    ])
    current_branch = _run_git(["branch", "--show-current"])
    last_tag = _run_git(["describe", "--tags", "--abbrev=0"]) or "no tags yet"
    changed_files = _run_git([
        "diff", f"HEAD~{min(since_commits, 5)}..HEAD", "--name-only",
    ])

    return {
        "available": True,
        "branch": current_branch or "main",
        "last_tag": last_tag,
        "recent_commits": log,
        "diff_stat": diff_stat,
        "changed_files": changed_files,
    }


def has_meaningful_changes(git_info: dict) -> bool:
    """Return True if there is anything worth documenting."""
    if not git_info.get("available"):
        return False
    return bool(git_info.get("recent_commits") or git_info.get("changed_files"))


# ---------------------------------------------------------------------------
# Project scanner
# ---------------------------------------------------------------------------

def scan_structure(root: Path, prefix: str = "", depth: int = 0, max_depth: int = 4) -> list[str]:
    """Return a tree-like list of paths, respecting ignore patterns."""
    if depth > max_depth:
        return []

    lines: list[str] = []
    try:
        entries = sorted(root.iterdir(), key=lambda p: (p.is_file(), p.name))
    except PermissionError:
        return []

    visible = [e for e in entries if not any(
        e.name == pat or e.match(pat) for pat in IGNORE_PATTERNS
    )]

    for i, entry in enumerate(visible):
        is_last = i == len(visible) - 1
        connector = "+-- " if is_last else "|-- "
        lines.append(f"{prefix}{connector}{entry.name}")
        if entry.is_dir():
            extension = "    " if is_last else "|   "
            lines.extend(scan_structure(entry, prefix + extension, depth + 1, max_depth))

    return lines


def build_structure_text(root: Path) -> str:
    lines = [root.name + "/"] + scan_structure(root)
    return "\n".join(lines)


def read_context_files(root: Path) -> str:
    """Read key source files and return them as a single string."""
    parts: list[str] = []
    for rel_path in CONTEXT_FILES:
        full = root / rel_path
        if not full.exists():
            continue
        try:
            content = full.read_text(encoding="utf-8")
            # Truncate very large files
            if len(content) > 3000:
                content = content[:3000] + "\n... [truncated]"
            parts.append(f"### {rel_path}\n```\n{content}\n```")
        except Exception:
            pass
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# OpenAI-powered README generator
# ---------------------------------------------------------------------------

def _strip_code_fence(text: str) -> str:
    """Usuwa ```markdown ... ``` jeśli model owinął output blokiem kodu."""
    text = text.strip()
    if text.startswith("```"):
        # Usuń pierwszą linię (```markdown lub ```)
        text = text.split("\n", 1)[1] if "\n" in text else ""
        # Usuń zamykający ```
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3].rstrip()
    return text


def build_user_prompt(
    structure: str,
    git_info: dict,
    source_context: str,
    output_file: str,
) -> str:
    git_section = ""
    if git_info.get("available"):
        git_section = f"""
## Recent Git Activity
Branch: {git_info['branch']}
Last tag: {git_info['last_tag']}

### Commits ({len(git_info['recent_commits'].splitlines())} shown):
{git_info['recent_commits']}

### Changed files:
{git_info['changed_files'] or 'none'}

### Diff stat:
{git_info['diff_stat'] or 'none'}
"""
    else:
        git_section = "Git is not available or the directory is not a repository."

    return f"""Generate a complete README.md for the project described below.
Output file will be saved as: {output_file}
Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M')}

---
## Project File Structure
```
{structure}
```

---
{git_section}

---
## Key Source Files
{source_context}

---
Generate the full README.md now. Start directly with the markdown content (do not add any preamble).
"""


async def generate_readme(
    client: AsyncOpenAI,
    model: str,
    structure: str,
    git_info: dict,
    source_context: str,
    output_file: str,
) -> str:
    logger.info("Sending context to OpenAI, generating README…")
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": README_SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(
                structure, git_info, source_context, output_file,
            )},
        ],
        temperature=0.4,
        max_tokens=4096,
    )
    return _strip_code_fence(response.choices[0].message.content or "")


def build_initial_prompt(structure: str, source_context: str, output_file: str) -> str:
    return f"""Generate the initial README.md for the project described below.
This is the FIRST time documentation is being created for this project.
Output file: {output_file}
Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M')}

---
## Project File Structure
```
{structure}
```

---
## Full Source Files
{source_context}

---
Generate the complete initial README.md now. Output raw Markdown only."""


async def generate_initial_readme(
    client: AsyncOpenAI,
    model: str,
    structure: str,
    source_context: str,
    output_file: str,
) -> str:
    logger.info("Sending context to OpenAI, generating initial README…")
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": INITIAL_README_SYSTEM_PROMPT},
            {"role": "user", "content": build_initial_prompt(
                structure, source_context, output_file,
            )},
        ],
        temperature=0.3,
        max_tokens=4096,
    )
    return _strip_code_fence(response.choices[0].message.content or "")


# ---------------------------------------------------------------------------
# Main agent
# ---------------------------------------------------------------------------

class DocsAgent:
    """Agent that scans the project and keeps README.md up to date."""

    def __init__(
        self,
        output_file: str = "README.md",
        since_commits: int = 20,
        force: bool = False,
        initial: bool = False,
        model: str = "gpt-4o",
    ):
        self.output_path = PROJECT_ROOT / output_file
        self.since_commits = since_commits
        self.force = force
        self.initial = initial
        self.model = model

        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            logger.error(
                "OPENAI_API_KEY not set. Add it to your .env file or environment."
            )
            sys.exit(1)

        self.client = AsyncOpenAI(api_key=api_key)

    async def run_initial(self) -> None:
        """Generate a comprehensive first-time README from scratch."""
        logger.info("=== Docs Agent — initial README generation ===")

        # Check if README already exists and warn
        if self.output_path.exists():
            logger.warning(
                f"{self.output_path.name} already exists and will be overwritten. "
                "Pass a different --output to keep the original."
            )

        logger.info("Scanning project structure…")
        structure = build_structure_text(PROJECT_ROOT)

        logger.info("Reading source files for context…")
        source_context = read_context_files(PROJECT_ROOT)

        readme_content = await generate_initial_readme(
            self.client,
            self.model,
            structure,
            source_context,
            self.output_path.name,
        )

        if not readme_content.strip():
            logger.error("OpenAI returned an empty response. Aborting.")
            sys.exit(1)

        self.output_path.write_text(readme_content, encoding="utf-8")
        logger.info(f"Initial README written to: {self.output_path}")
        logger.info("=== Docs Agent finished ===")

    async def run(self) -> None:
        logger.info("=== Docs Agent starting ===")

        # 1. Collect git info
        logger.info("Collecting git history…")
        git_info = get_git_info(self.since_commits)
        if git_info.get("available"):
            logger.info(
                f"Branch: {git_info['branch']} | "
                f"Last tag: {git_info['last_tag']} | "
                f"Commits shown: {len(git_info['recent_commits'].splitlines())}"
            )
        else:
            logger.warning(f"Git unavailable: {git_info.get('reason', 'unknown')}")

        # 2. Check if there's anything new (unless --force)
        if not self.force and not has_meaningful_changes(git_info):
            logger.info("No meaningful git changes detected. Use --force to regenerate anyway.")
            return

        # 3. Scan project structure
        logger.info("Scanning project structure…")
        structure = build_structure_text(PROJECT_ROOT)

        # 4. Read key source files
        logger.info("Reading source files for context…")
        source_context = read_context_files(PROJECT_ROOT)

        # 5. Generate README via OpenAI
        readme_content = await generate_readme(
            self.client,
            self.model,
            structure,
            git_info,
            source_context,
            self.output_path.name,
        )

        if not readme_content.strip():
            logger.error("OpenAI returned an empty response. Aborting.")
            sys.exit(1)

        # 6. Write output
        self.output_path.write_text(readme_content, encoding="utf-8")
        logger.info(f"README written to: {self.output_path}")
        logger.info("=== Docs Agent finished ===")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Docs Agent — aktualizuje README.md na podstawie zmian w kodzie.\n"
            "Docs Agent — updates README.md based on code changes."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--output",
        default="README.md",
        metavar="FILE",
        help="Output markdown file (default: README.md)",
    )
    parser.add_argument(
        "--since",
        type=int,
        default=20,
        metavar="N",
        help="Number of recent commits to inspect (default: 20)",
    )
    parser.add_argument(
        "--initial",
        action="store_true",
        help=(
            "Generate a complete initial README from scratch "
            "(ignores git history, uses a detailed first-time prompt)"
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate README even if no git changes are detected",
    )
    parser.add_argument(
        "--model",
        default="gpt-4o",
        metavar="MODEL",
        help="OpenAI model to use (default: gpt-4o)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    agent = DocsAgent(
        output_file=args.output,
        since_commits=args.since,
        force=args.force,
        initial=args.initial,
        model=args.model,
    )
    if args.initial:
        asyncio.run(agent.run_initial())
    else:
        asyncio.run(agent.run())
