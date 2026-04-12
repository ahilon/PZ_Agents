"""Project Init Agent — inicjalizacja projektu i kontrola jakości przed commitem."""
import asyncio
import json
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from src.agents.base_agent import BaseAgent
from src.models.agent import AgentConfig, AgentType, Task

logger = logging.getLogger(__name__)

# Konfiguracje narzędzi dodawane do pyproject.toml
_TOOL_CONFIGS = """
[tool.isort]
profile = "black"
line_length = 120
known_first_party = ["src"]
skip = [".venv", "venv", "__pycache__"]

[tool.pylint.main]
max-line-length = 120
disable = ["C0114", "C0115", "C0116"]
ignore-paths = [".venv", "venv"]

[tool.pylint.format]
max-line-length = 120
"""

_GITIGNORE_TEMPLATE = """\
# Zmienne środowiskowe / Secrets
.env
.env.*
!.env.example

# Python
__pycache__/
*.py[cod]
*.pyo
dist/
build/
*.egg-info/

# Poetry / virtualenv
.venv/
venv/
env/
.python-version

# Testy i pokrycie
.pytest_cache/
.coverage
htmlcov/
coverage.xml

# Linter / formatter
.mypy_cache/
.ruff_cache/
.pylintrc.bak

# IDE — VS Code
.vscode/*
!.vscode/extensions.json
!.vscode/settings.json

# IDE — JetBrains
.idea/
*.iml

# System
Thumbs.db
.DS_Store
*~
*.log
*.tmp
"""


def _run(cmd: list[str], cwd: Path) -> dict:
    try:
        result = subprocess.run(
            cmd, cwd=str(cwd), capture_output=True, text=True, timeout=60,
        )
        return {
            "command": " ".join(cmd),
            "output": (result.stdout + result.stderr).strip(),
            "returncode": result.returncode,
            "success": result.returncode == 0,
        }
    except FileNotFoundError:
        return {"command": " ".join(cmd), "output": f"Komenda nie znaleziona: {cmd[0]}", "returncode": -1, "success": False}
    except subprocess.TimeoutExpired:
        return {"command": " ".join(cmd), "output": "TIMEOUT (60s)", "returncode": -1, "success": False}


class ProjectInitAgent(BaseAgent):
    """
    Agent inicjalizacji projektu — dwa tryby:
    - init:   tworzy .gitignore, konfigurację narzędzi, PROJECT.md, README przez docs_agent
    - commit: isort → pylint → AI-fix → GitAgent commit+push
    """

    async def _process_task(self, task: Task) -> Any:
        mode = task.parameters.get("mode", "init")
        if mode == "init":
            return await asyncio.to_thread(self._init_project, task)
        elif mode == "commit":
            return await self._commit_with_checks(task)
        else:
            return {"status": "failed", "summary": f"Nieznany tryb: '{mode}'. Dostępne: init, commit."}

    # ------------------------------------------------------------------
    # Tryb INIT
    # ------------------------------------------------------------------

    def _init_project(self, task: Task) -> dict:
        p = task.parameters
        repo_path    = Path(p.get("repo_path", ".")).resolve()
        project_name = p.get("project_name", repo_path.name)
        project_desc = p.get("description", task.description or "Projekt Python")
        steps: list[dict] = []

        # 1. .gitignore
        steps.append(self._create_gitignore(repo_path))

        # 2. Konfiguracja narzędzi w pyproject.toml
        steps.append(self._add_tool_configs(repo_path))

        # 3. Instalacja narzędzi
        steps.append(self._install_tools(repo_path))

        # 4. PROJECT.md
        steps.append(self._create_project_md(repo_path, project_name, project_desc))

        # 5. docs_agent --initial (subprocess, może być długie)
        steps.append(self._run_docs_agent_initial(repo_path))

        failed = [s for s in steps if not s.get("success", True)]
        return {
            "mode": "init",
            "repo_path": str(repo_path),
            "project_name": project_name,
            "steps": steps,
            "summary": (
                f"Projekt '{project_name}' zainicjalizowany. "
                f"{len(steps) - len(failed)}/{len(steps)} kroków zakończonych sukcesem."
            ),
            "status": "completed" if not failed else "partial",
        }

    def _create_gitignore(self, repo_path: Path) -> dict:
        path = repo_path / ".gitignore"
        if path.exists():
            return {"step": "gitignore", "success": True, "note": "Już istnieje — pominięto"}
        path.write_text(_GITIGNORE_TEMPLATE, encoding="utf-8")
        return {"step": "gitignore", "success": True, "note": f"Utworzono {path}"}

    def _add_tool_configs(self, repo_path: Path) -> dict:
        pyproject = repo_path / "pyproject.toml"
        if not pyproject.exists():
            return {"step": "tool_configs", "success": False, "note": "Brak pyproject.toml"}

        content = pyproject.read_text(encoding="utf-8")
        added = []
        if "[tool.isort]" not in content:
            content += "\n[tool.isort]\nprofile = \"black\"\nline_length = 120\nknown_first_party = [\"src\"]\nskip = [\".venv\", \"venv\", \"__pycache__\"]\n"
            added.append("isort")
        if "[tool.pylint" not in content:
            content += "\n[tool.pylint.main]\nmax-line-length = 120\ndisable = [\"C0114\", \"C0115\", \"C0116\"]\nignore-paths = [\".venv\", \"venv\"]\n\n[tool.pylint.format]\nmax-line-length = 120\n"
            added.append("pylint")

        if added:
            pyproject.write_text(content, encoding="utf-8")
            return {"step": "tool_configs", "success": True, "note": f"Dodano konfigurację: {', '.join(added)}"}
        return {"step": "tool_configs", "success": True, "note": "Konfiguracje już istnieją"}

    def _install_tools(self, repo_path: Path) -> dict:
        result = _run(["poetry", "add", "--group", "dev", "pylint", "isort"], repo_path)
        return {"step": "install_tools", "success": result["success"], "note": result["output"][:200]}

    def _create_project_md(self, repo_path: Path, name: str, description: str) -> dict:
        path = repo_path / "PROJECT.md"
        if path.exists():
            return {"step": "project_md", "success": True, "note": "Już istnieje — pominięto"}

        content = f"""# {name}

{description}

## Cel projektu / Project Goal

> Uzupełnij opis projektu / Fill in the project description

## Główne funkcje / Main Features

-

## Stack technologiczny / Tech Stack

- Python 3.12+
- Poetry

## Uruchomienie / Running

```bash
poetry install
cp .env.example .env
poetry run python main.py
```

---
*Wygenerowano automatycznie przez ProjectInitAgent dnia {datetime.now().strftime('%Y-%m-%d')}*
"""
        path.write_text(content, encoding="utf-8")
        return {"step": "project_md", "success": True, "note": f"Utworzono {path}"}

    def _run_docs_agent_initial(self, repo_path: Path) -> dict:
        # docs_agent.py może być w katalogu docelowym lub w katalogu tego skryptu (project root)
        candidates = [
            repo_path / "docs_agent.py",
            Path(__file__).resolve().parents[2] / "docs_agent.py",
        ]
        docs_agent_path = next((p for p in candidates if p.exists()), None)
        if not docs_agent_path:
            return {
                "step": "docs_agent_initial",
                "success": False,
                "note": "docs_agent.py nie znaleziony — pomiń lub uruchom ręcznie.",
            }
        result = _run(
            [sys.executable, str(docs_agent_path), "--initial"],
            repo_path,
        )
        return {
            "step": "docs_agent_initial",
            "success": result["success"],
            "note": result["output"][-300:] if result["output"] else "brak outputu",
        }

    # ------------------------------------------------------------------
    # Tryb COMMIT — isort → pylint → AI-fix → GitAgent
    # ------------------------------------------------------------------

    async def _commit_with_checks(self, task: Task) -> dict:
        p = task.parameters
        repo_path = Path(p.get("repo_path", ".")).resolve()
        files     = p.get("files", ["."])

        checks: dict = {}
        extra_fixed_files: list[str] = []

        # 1. isort
        isort = await asyncio.to_thread(self._run_isort, repo_path, files)
        checks["isort"] = isort
        if isort.get("files_changed"):
            extra_fixed_files.extend(isort["files_changed"])

        # 2. pylint
        pylint = await asyncio.to_thread(self._run_pylint, repo_path, files)
        checks["pylint"] = pylint

        # 3. AI-fix pylintowych problemów C/R
        if pylint.get("fixable_issues") and self._llm:
            fix_result = await self._ai_fix_pylint(repo_path, pylint["fixable_issues"])
            checks["pylint_ai_fix"] = fix_result
            extra_fixed_files.extend(fix_result.get("fixed_files", []))

            # Re-run pylint po naprawie
            pylint2 = await asyncio.to_thread(self._run_pylint, repo_path, files)
            checks["pylint_after_fix"] = pylint2

        # 4. Zatrzymaj jeśli są błędy E/F
        fatal = pylint.get("fatal_issues", [])
        if fatal:
            return {
                "mode": "commit",
                "checks": checks,
                "files_ready_to_commit": [],
                "warnings": [f"Zatrzymano — pylint ma błędy krytyczne: {len(fatal)} issue(s)"],
                "status": "failed",
                "summary": f"BLOKADA: {len(fatal)} błędów E/F w pylint. Napraw ręcznie przed commitem.",
            }

        # 5. Połącz pliki do commitu
        all_files = list(set(files + extra_fixed_files))
        if "." in all_files:
            all_files = ["."]

        # 6. GitAgent commit+push
        git_result = await self._run_git_agent(task, all_files)

        return {
            "mode": "commit",
            "checks": checks,
            "files_ready_to_commit": all_files,
            "warnings": pylint.get("warning_issues", [])[:5],
            "git": git_result,
            "status": "completed" if git_result.get("success") else "failed",
            "summary": (
                f"isort: {checks['isort']['status']} | "
                f"pylint: {pylint.get('score', '?')}/10 | "
                f"git: {git_result.get('summary', '?')}"
            ),
        }

    # --- isort ---

    def _run_isort(self, repo_path: Path, files: list[str]) -> dict:
        targets = files if files != ["."] else ["."]

        # Sprawdź czy są zmiany
        check = _run(["isort", "--check-only"] + targets, repo_path)
        if check["success"]:
            return {"status": "ok", "files_changed": [], "output": "Importy są już posortowane"}

        # Napraw
        fix = _run(["isort"] + targets, repo_path)
        if not fix["success"]:
            return {"status": "error", "files_changed": [], "output": fix["output"]}

        # Znajdź zmienione pliki
        changed = _run(["git", "diff", "--name-only"], repo_path)
        changed_files = [f for f in changed["output"].splitlines() if f.endswith(".py")]
        return {"status": "fixed", "files_changed": changed_files, "output": f"Posortowano importy w {len(changed_files)} plikach"}

    # --- pylint ---

    def _run_pylint(self, repo_path: Path, files: list[str]) -> dict:
        targets = [f for f in files if f != "."] or ["src"]
        result = _run(["pylint"] + targets + ["--output-format=json", "--score=yes"], repo_path)

        issues = []
        score = None

        # Parsuj JSON output
        try:
            for line in result["output"].splitlines():
                if line.startswith("["):
                    issues = json.loads(line)
                    break
        except json.JSONDecodeError:
            pass

        # Wyciągnij score z output
        for line in result["output"].splitlines():
            if "Your code has been rated at" in line:
                try:
                    score = float(line.split("rated at")[1].split("/")[0].strip())
                except (ValueError, IndexError):
                    pass

        fixable   = [i for i in issues if i.get("type") in ("convention", "refactor")]
        warnings  = [i for i in issues if i.get("type") == "warning"]
        fatals    = [i for i in issues if i.get("type") in ("error", "fatal")]

        status = "ok" if not issues else ("issues" if not fatals else "fatal")

        return {
            "status": status,
            "score": score,
            "total_issues": len(issues),
            "fixable_issues": fixable,
            "warning_issues": [f"{i['path']}:{i['line']} {i['message']}" for i in warnings[:10]],
            "fatal_issues": [f"{i['path']}:{i['line']} {i['message']}" for i in fatals],
        }

    # --- AI fix pylint ---

    async def _ai_fix_pylint(self, repo_path: Path, issues: list[dict]) -> dict:
        # Grupuj po pliku
        by_file: dict[str, list[dict]] = {}
        for issue in issues:
            path = issue.get("path", "")
            by_file.setdefault(path, []).append(issue)

        fixed_files: list[str] = []

        for rel_path, file_issues in by_file.items():
            full_path = repo_path / rel_path
            if not full_path.exists():
                continue

            original = full_path.read_text(encoding="utf-8")
            issues_text = "\n".join(
                f"Linia {i['line']}: [{i['message-id']}] {i['message']}"
                for i in file_issues[:20]
            )

            prompt = (
                f"Napraw poniższe problemy pylint w pliku Python.\n"
                f"Zmieniaj TYLKO to co jest wymienione — nie refaktoryzuj reszty kodu.\n\n"
                f"Problemy:\n{issues_text}\n\n"
                f"Kod pliku:\n```python\n{original[:4000]}\n```\n\n"
                f"Zwróć TYLKO poprawiony kod Pythona, bez żadnych objaśnień ani markdown."
            )

            fixed_code = await self._call_llm(prompt, response_json=False)

            if fixed_code and fixed_code.strip() and fixed_code != original:
                # Usuń ewentualne ```python ``` owinięcie
                if fixed_code.startswith("```"):
                    lines = fixed_code.splitlines()
                    fixed_code = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

                full_path.write_text(fixed_code, encoding="utf-8")
                fixed_files.append(rel_path)
                logger.info(f"AI naprawiło: {rel_path}")

        return {
            "fixed_files": fixed_files,
            "files_attempted": list(by_file.keys()),
            "note": f"AI naprawiło {len(fixed_files)}/{len(by_file)} plików",
        }

    # --- GitAgent ---

    async def _run_git_agent(self, original_task: Task, files: list[str]) -> dict:
        from src.agents.git_agent import GitAgent
        from src.prompts import GIT_AGENT_PROMPT

        config = AgentConfig(
            name="Git Bot (ProjectInit)",
            agent_type=AgentType.GIT,
            description="Commit po sprawdzeniu jakości kodu",
            system_prompt=GIT_AGENT_PROMPT,
        )
        agent = GitAgent(config)

        git_task = Task(
            id=f"git_{original_task.id}",
            name=original_task.name,
            description=original_task.description,
            agent_type=AgentType.GIT,
            parameters={
                "mode": "commit",
                "repo_path": original_task.parameters.get("repo_path", "."),
                "files": files,
                "push": original_task.parameters.get("push", False),
                "branch": original_task.parameters.get("branch"),
                "message": original_task.parameters.get("message"),
            },
        )

        response = await agent.execute(git_task)
        if response.success and response.result:
            r = response.result
            return {
                "success": True,
                "branch": r.get("branch"),
                "commit_hash": r.get("commit_hash", "")[:8],
                "pushed": r.get("pushed"),
                "pr": r.get("pr", {}),
                "summary": r.get("summary"),
            }
        return {"success": False, "summary": response.error or "GitAgent nieudany"}
