"""Git Agent — zarządzanie repozytorium, commity na osobnych gałęziach."""
import asyncio
import logging
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse

import requests
from dotenv import load_dotenv
from openai import AsyncOpenAI

from src.models.agent import Task
from src.agents.base_agent import BaseAgent

load_dotenv()

logger = logging.getLogger(__name__)

DEFAULT_BOT_NAME  = os.getenv("GIT_BOT_NAME",  "agents-bot")
DEFAULT_BOT_EMAIL = os.getenv("GIT_BOT_EMAIL",  "agents-bot@users.noreply.github.com")
DEFAULT_BOT_TOKEN = os.getenv("GIT_BOT_TOKEN",  "")
OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY", "")

# Mapowanie rozszerzeń plików → prefix conventional commit
_EXT_PREFIX = {
    "md": "docs", "rst": "docs", "txt": "docs",
    "py": "feat",  "js": "feat",  "ts": "feat",
    "json": "chore", "toml": "chore", "yaml": "chore", "yml": "chore",
    "env": "chore", "cfg": "chore", "ini": "chore",
    "sh": "chore", "bat": "chore",
    "css": "style", "scss": "style",
    "sql": "feat",
}
_TEST_PATTERN = re.compile(r"test_|_test\.|spec\.")


# ---------------------------------------------------------------------------
# Pomocnicze — git, token, branch, commit message
# ---------------------------------------------------------------------------

def _inject_token(url: str, username: str, token: str) -> str:
    """https://github.com/x/y → https://username:token@github.com/x/y"""
    if not token or not url.startswith("https://"):
        return url
    p = urlparse(url)
    netloc = f"{username}:{token}@{p.hostname}{(':' + str(p.port)) if p.port else ''}"
    return urlunparse(p._replace(netloc=netloc))


def _mask(text: str, token: str) -> str:
    return text.replace(token, "***") if token else text


def _run(cmd: list[str], cwd: str | Path, token: str = "") -> dict:
    try:
        result = subprocess.run(
            cmd, cwd=str(cwd), capture_output=True, text=True, timeout=30,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
        return {
            "command": _mask(" ".join(cmd), token),
            "output":  _mask((result.stdout + result.stderr).strip(), token),
            "success": result.returncode == 0,
        }
    except subprocess.TimeoutExpired:
        return {"command": _mask(" ".join(cmd), token), "output": "TIMEOUT",                       "success": False}
    except FileNotFoundError:
        return {"command": " ".join(cmd),               "output": "git nie znaleziony w PATH",     "success": False}


def _slugify(text: str, max_len: int = 30) -> str:
    """Zamienia dowolny tekst na kebab-case nadający się do nazwy gałęzi."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s-]+", "-", text).strip("-")
    return text[:max_len].rstrip("-")


def _auto_branch_name(description: str = "") -> str:
    """bot/YYYY-MM-DD-krotki-opis"""
    date = datetime.now().strftime("%Y-%m-%d")
    slug = _slugify(description) if description else "update"
    return f"bot/{date}-{slug}"


def _rule_based_message(files: list[str]) -> str:
    """Generuje commit message na podstawie listy plików (bez AI)."""
    if not files:
        return "chore: automated update"

    # Wykryj prefix
    prefixes: dict[str, int] = {}
    for f in files:
        ext = Path(f).suffix.lstrip(".")
        if _TEST_PATTERN.search(Path(f).name):
            prefix = "test"
        else:
            prefix = _EXT_PREFIX.get(ext, "chore")
        prefixes[prefix] = prefixes.get(prefix, 0) + 1
    top_prefix = max(prefixes, key=lambda k: prefixes[k])

    # Zbuduj listę nazw plików
    names = [Path(f).name for f in files]
    if len(names) == 1:
        scope = names[0]
    elif len(names) <= 3:
        scope = ", ".join(names)
    else:
        scope = f"{names[0]}, {names[1]} (+{len(names) - 2})"

    return f"{top_prefix}: update {scope}"


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class GitAgent(BaseAgent):
    """
    Agent Git — tryby:
    - commit: nowy commit na osobnej gałęzi bot/YYYY-MM-DD-opis (bez merge)
    - init:   inicjalizuje repozytorium i tworzy pierwszy commit

    Konfiguracja z .env:
        GIT_BOT_NAME   — nazwa commitera
        GIT_BOT_EMAIL  — email commitera (noreply GitHub)
        GIT_BOT_TOKEN  — PAT konta bota (używany tylko przy push)
        OPENAI_API_KEY — jeśli ustawiony, generuje AI commit message
    """

    def __init__(self, config):
        super().__init__(config)
        self._openai = AsyncOpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    async def _process_task(self, task: Task) -> Any:
        mode = task.parameters.get("mode", "commit")

        # Uzupełnij branch i message przed wejściem w sync thread
        if mode == "commit":
            if not task.parameters.get("branch"):
                desc = task.parameters.get("description", task.name)
                task.parameters["branch"] = _auto_branch_name(desc)

            if not task.parameters.get("message"):
                task.parameters["message"] = await self._generate_message(task)

        elif mode == "init":
            if not task.parameters.get("message"):
                task.parameters["message"] = await self._generate_message(task)

        if mode == "init":
            return await asyncio.to_thread(self._init_repo, task)
        elif mode == "commit":
            return await asyncio.to_thread(self._create_commit, task)
        else:
            return {"status": "failed", "summary": f"Nieznany tryb: '{mode}'. Dostępne: init, commit."}

    # ------------------------------------------------------------------
    # Generowanie commit message
    # ------------------------------------------------------------------

    async def _generate_message(self, task: Task) -> str:
        """AI jeśli dostępne, fallback rule-based."""
        files = task.parameters.get("files", ["."])
        description = task.description or task.name

        if self._openai:
            try:
                return await self._ai_message(files, description)
            except Exception as e:
                logger.warning(f"AI commit message nieudany ({e}), używam rule-based.")

        return _rule_based_message(files if files != ["."] else [])

    async def _ai_message(self, files: list[str], description: str) -> str:
        """Generuje krótką commit message przez OpenAI."""
        file_list = ", ".join(Path(f).name for f in files[:10]) if files != ["."] else "wiele plików"
        resp = await self._openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": (
                    f"Wygeneruj krótką commit message (max 72 znaki) w formacie conventional commits "
                    f"(feat/fix/docs/chore/refactor/test: opis).\n"
                    f"Zmienione pliki: {file_list}\n"
                    f"Opis zadania: {description}\n"
                    f"Zwróć TYLKO sam tekst wiadomości, nic więcej."
                ),
            }],
            temperature=0.2,
            max_tokens=60,
        )
        msg = resp.choices[0].message.content.strip().strip('"').strip("'")
        return msg[:72]  # hard limit

    # ------------------------------------------------------------------
    # Tryb INIT
    # ------------------------------------------------------------------

    @staticmethod
    def _configure_git_identity(repo_path: Path, bot_name: str, bot_email: str, token: str) -> list[dict]:
        """Konfiguruje tożsamość git dla repozytorium (lokalnie)."""
        return [
            _run(["git", "config", "user.name",  bot_name],  repo_path, token),
            _run(["git", "config", "user.email", bot_email], repo_path, token),
        ]

    def _init_repo(self, task: Task) -> dict:
        p = task.parameters
        repo_path  = Path(p.get("repo_path", ".")).resolve()
        files      = p.get("files", ["."])
        message    = p["message"]
        remote_url = p.get("remote_url")
        bot_name   = p.get("bot_name",  DEFAULT_BOT_NAME)
        bot_email  = p.get("bot_email", DEFAULT_BOT_EMAIL)
        token      = p.get("token",     DEFAULT_BOT_TOKEN)
        push       = p.get("push", False)
        steps: list[dict] = []

        steps.append(_run(["git", "init", "-b", "main"], repo_path, token))
        if not steps[-1]["success"]:
            steps.append(_run(["git", "init"], repo_path, token))
            if not steps[-1]["success"]:
                return self._fail(steps, "git init nieudany", token)

        steps += self._configure_git_identity(repo_path, bot_name, bot_email, token)
        for f in files:
            steps.append(_run(["git", "add", f], repo_path, token))

        steps.append(_run(["git", "commit", "-m", message], repo_path, token))
        if not steps[-1]["success"]:
            return self._fail(steps, "git commit nieudany", token)

        commit_hash = _run(["git", "rev-parse", "HEAD"], repo_path, token).get("output", "?")

        pushed = False
        clean_url = None
        if remote_url:
            clean_url = remote_url
            auth_url  = _inject_token(remote_url, bot_name, token)
            steps.append(_run(["git", "remote", "add", "origin", auth_url], repo_path, token))
            if push and token:
                steps.append(_run(["git", "push", "-u", "origin", "main"], repo_path, token))
                pushed = steps[-1]["success"]
            elif push:
                logger.warning("push=True ale GIT_BOT_TOKEN nie jest ustawiony.")

        return {
            "mode": "init", "repo_path": str(repo_path), "branch": "main",
            "commit_hash": commit_hash, "commit_message": message,
            "files_committed": self._committed_files(repo_path, token),
            "remote_url": clean_url, "pushed": pushed,
            "bot_name": bot_name, "bot_email": bot_email,
            "steps": steps,
            "summary": f"Repo zainicjalizowane. Commit: {commit_hash[:8]}. {'Wypchnięto.' if pushed else ''}".strip(),
            "status": "completed",
        }

    # ------------------------------------------------------------------
    # Tryb COMMIT
    # ------------------------------------------------------------------

    def _create_commit(self, task: Task) -> dict:
        p = task.parameters
        repo_path = Path(p.get("repo_path", ".")).resolve()
        files     = p.get("files", ["."])
        message   = p["message"]
        branch    = p["branch"]          # zawsze ustawiony przez _process_task
        push      = p.get("push", False)
        bot_name  = p.get("bot_name",  DEFAULT_BOT_NAME)
        bot_email = p.get("bot_email", DEFAULT_BOT_EMAIL)
        token     = p.get("token",     DEFAULT_BOT_TOKEN)
        steps: list[dict] = []

        if not _run(["git", "rev-parse", "--is-inside-work-tree"], repo_path, token)["success"]:
            return self._fail(steps, f"Nie jest repozytorium git: {repo_path}", token)

        steps += self._configure_git_identity(repo_path, bot_name, bot_email, token)

        steps.append(_run(["git", "checkout", "-b", branch], repo_path, token))
        if not steps[-1]["success"]:
            return self._fail(steps, f"Nie można utworzyć gałęzi: {branch}", token)

        for f in files:
            steps.append(_run(["git", "add", f], repo_path, token))

        steps.append(_run(["git", "commit", "-m", message], repo_path, token))
        if not steps[-1]["success"]:
            return self._fail(steps, "git commit nieudany — brak zmian do zacommitowania", token)

        commit_hash = _run(["git", "rev-parse", "HEAD"], repo_path, token).get("output", "?")

        pushed = False
        remote_url_clean = None
        if push and token:
            remote = _run(["git", "remote", "get-url", "origin"], repo_path, token)
            if remote["success"]:
                remote_url_clean = remote["output"]
                auth_url = _inject_token(remote_url_clean, bot_name, token)
                steps.append(_run(["git", "push", "-u", auth_url, branch], repo_path, token))
                pushed = steps[-1]["success"]
            else:
                logger.warning("Brak remote 'origin' — nie można wypchnąć.")
        elif push:
            logger.warning("push=True ale GIT_BOT_TOKEN nie jest ustawiony.")

        # Otwórz PR jeśli push się udał i create_pr=True
        pr_result: dict = {}
        create_pr = p.get("create_pr", True)
        base_branch = p.get("base_branch", "main")
        if pushed and create_pr and remote_url_clean:
            parsed = self._parse_repo(remote_url_clean)
            if parsed:
                owner, repo_name = parsed
                pr_body = p.get("pr_body", f"Automatyczny PR z gałęzi `{branch}`.\n\nCommit: `{commit_hash[:8]}`")
                pr_result = self._open_pr(owner, repo_name, token, branch, base_branch, message, pr_body)
                if pr_result.get("success"):
                    logger.info(f"PR otwarty: {pr_result['pr_url']}")
                else:
                    logger.warning(f"PR nieudany: {pr_result.get('error')}")

        summary = f"Commit {commit_hash[:8]} na '{branch}'. "
        if pushed:
            summary += "Wypchnięto. "
        if pr_result.get("success"):
            summary += f"PR #{pr_result['pr_number']}: {pr_result['pr_url']}"

        return {
            "mode": "commit", "repo_path": str(repo_path), "branch": branch,
            "commit_hash": commit_hash, "commit_message": message,
            "files_committed": self._committed_files(repo_path, token),
            "remote_url": remote_url_clean, "pushed": pushed,
            "pr": pr_result,
            "bot_name": bot_name, "bot_email": bot_email,
            "steps": steps,
            "summary": summary.strip(),
            "status": "completed",
        }

    # ------------------------------------------------------------------
    # Pull Request
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_repo(remote_url: str) -> tuple[str, str] | None:
        """Wyciąga (owner, repo) z URL remote git."""
        # https://github.com/owner/repo.git  lub  git@github.com:owner/repo.git
        m = re.search(r"github\.com[:/]([^/]+)/([^/.]+)", remote_url)
        return (m.group(1), m.group(2)) if m else None

    @staticmethod
    def _open_pr(owner: str, repo: str, token: str, head: str,
                 base: str, title: str, body: str) -> dict:
        """Tworzy Pull Request przez GitHub API."""
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
        resp = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            json={"title": title, "body": body, "head": head, "base": base},
            timeout=15,
        )
        if resp.status_code == 201:
            data = resp.json()
            return {"success": True, "pr_url": data["html_url"], "pr_number": data["number"]}
        return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _committed_files(repo_path: Path, token: str) -> list[str]:
        result = _run(["git", "show", "--stat", "--format=", "HEAD"], repo_path, token)
        return [
            line.strip().split(" | ")[0].strip()
            for line in result["output"].splitlines() if " | " in line
        ]

    @staticmethod
    def _fail(steps: list[dict], reason: str, token: str = "") -> dict:
        last = _mask(steps[-1]["output"], token) if steps else ""
        return {
            "mode": "unknown", "repo_path": "", "branch": "",
            "commit_hash": "brak", "commit_message": "",
            "files_committed": [], "remote_url": None, "pushed": False,
            "steps": steps,
            "summary": f"Błąd: {reason}. Output: {last}",
            "status": "failed",
        }
