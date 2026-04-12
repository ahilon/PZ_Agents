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

from src.models.agent import Task
from src.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

DEFAULT_BOT_NAME = os.getenv("GIT_BOT_NAME", "agents-bot")
DEFAULT_BOT_EMAIL = os.getenv("GIT_BOT_EMAIL", "agents-bot@users.noreply.github.com")
DEFAULT_BOT_TOKEN = os.getenv("GIT_BOT_TOKEN", "")


# ---------------------------------------------------------------------------
# Pomocnicze — token, URL, uruchamianie poleceń
# ---------------------------------------------------------------------------

def _inject_token(url: str, username: str, token: str) -> str:
    """Wstrzykuje dane uwierzytelniające do URL HTTPS.
    https://github.com/owner/repo → https://username:token@github.com/owner/repo
    """
    if not token or not url.startswith("https://"):
        return url
    parsed = urlparse(url)
    authed = parsed._replace(netloc=f"{username}:{token}@{parsed.hostname}{(':' + str(parsed.port)) if parsed.port else ''}")
    return urlunparse(authed)


def _mask(text: str, token: str) -> str:
    """Zastępuje token w tekście przez '***' — token nigdy nie trafia do logów."""
    if not token:
        return text
    return text.replace(token, "***")


def _run(cmd: list[str], cwd: str | Path, token: str = "") -> dict:
    """Uruchamia polecenie git i zwraca wynik z zamaskowanym tokenem."""
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},  # nie pytaj o hasło interaktywnie
        )
        raw_output = (result.stdout + result.stderr).strip()
        return {
            "command": _mask(" ".join(cmd), token),
            "output": _mask(raw_output, token),
            "success": result.returncode == 0,
        }
    except subprocess.TimeoutExpired:
        return {"command": _mask(" ".join(cmd), token), "output": "TIMEOUT", "success": False}
    except FileNotFoundError:
        return {"command": " ".join(cmd), "output": "git nie znalezione w PATH", "success": False}


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class GitAgent(BaseAgent):
    """
    Agent Git — dwa tryby:
    - init:   inicjalizuje nowe repozytorium i tworzy pierwszy commit
    - commit: tworzy nowy commit na osobnej gałęzi (bez merge)

    Autentykacja przy push:
    - Token pobierany z parametrów zadania lub zmiennej GIT_BOT_TOKEN
    - Wstrzykiwany do URL tylko przy wywołaniu git push
    - Nigdy nie pojawia się w logach ani wynikach
    """

    async def _process_task(self, task: Task) -> Any:
        mode = task.parameters.get("mode", "commit")
        if mode == "init":
            return await asyncio.to_thread(self._init_repo, task)
        elif mode == "commit":
            return await asyncio.to_thread(self._create_commit, task)
        else:
            return {
                "status": "failed",
                "summary": f"Nieznany tryb: '{mode}'. Dostępne: 'init', 'commit'.",
            }

    # ------------------------------------------------------------------
    # Tryb INIT
    # ------------------------------------------------------------------

    def _init_repo(self, task: Task) -> dict:
        """Inicjalizuje nowe repo git i tworzy pierwszy commit."""
        p = task.parameters
        repo_path = Path(p.get("repo_path", ".")).resolve()
        files = p.get("files", ["."])
        message = p.get("message", f"chore: initial commit [{datetime.now().strftime('%Y-%m-%d')}]")
        remote_url: str | None = p.get("remote_url")
        bot_name = p.get("bot_name", DEFAULT_BOT_NAME)
        bot_email = p.get("bot_email", DEFAULT_BOT_EMAIL)
        token = p.get("token", DEFAULT_BOT_TOKEN)
        push = p.get("push", False)

        steps: list[dict] = []

        steps.append(_run(["git", "init", "-b", "main"], repo_path, token))
        if not steps[-1]["success"]:
            # Starsze git nie obsługuje -b, spróbuj bez
            steps.append(_run(["git", "init"], repo_path, token))
            if not steps[-1]["success"]:
                return self._fail(steps, "git init nieudany", token)

        steps.append(_run(["git", "config", "user.name", bot_name], repo_path, token))
        steps.append(_run(["git", "config", "user.email", bot_email], repo_path, token))

        for f in files:
            steps.append(_run(["git", "add", f], repo_path, token))

        steps.append(_run(["git", "commit", "-m", message], repo_path, token))
        if not steps[-1]["success"]:
            return self._fail(steps, "git commit nieudany", token)

        hash_result = _run(["git", "rev-parse", "HEAD"], repo_path, token)
        commit_hash = hash_result["output"] if hash_result["success"] else "nieznany"

        pushed = False
        if remote_url:
            clean_url = remote_url  # URL bez tokenu — do przechowania w wynikach
            auth_url = _inject_token(remote_url, bot_name, token)
            steps.append(_run(["git", "remote", "add", "origin", auth_url], repo_path, token))

            if push and token:
                steps.append(_run(["git", "push", "-u", "origin", "main"], repo_path, token))
                pushed = steps[-1]["success"]
            elif push and not token:
                logger.warning("push=True ale GIT_BOT_TOKEN nie jest ustawiony — pomijam push")
        else:
            clean_url = None

        committed_files = self._list_committed_files(repo_path, token)

        return {
            "mode": "init",
            "repo_path": str(repo_path),
            "branch": "main",
            "commit_hash": commit_hash,
            "commit_message": message,
            "files_committed": committed_files,
            "remote_url": clean_url,
            "pushed": pushed,
            "bot_name": bot_name,
            "bot_email": bot_email,
            "steps": steps,
            "summary": (
                f"Repozytorium zainicjalizowane w {repo_path}. "
                f"Commit: {commit_hash[:8]}. "
                f"{'Wypchnięto na remote.' if pushed else ''}"
            ).strip(),
            "status": "completed",
        }

    # ------------------------------------------------------------------
    # Tryb COMMIT
    # ------------------------------------------------------------------

    def _create_commit(self, task: Task) -> dict:
        """Tworzy nowy commit na osobnej gałęzi — bez merge do main."""
        p = task.parameters
        repo_path = Path(p.get("repo_path", ".")).resolve()
        files = p.get("files", ["."])
        message = p.get("message", f"bot: automated update [{datetime.now().strftime('%Y-%m-%d %H:%M')}]")
        branch = p.get("branch") or f"bot/update-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        push = p.get("push", False)
        bot_name = p.get("bot_name", DEFAULT_BOT_NAME)
        bot_email = p.get("bot_email", DEFAULT_BOT_EMAIL)
        token = p.get("token", DEFAULT_BOT_TOKEN)

        steps: list[dict] = []

        check = _run(["git", "rev-parse", "--is-inside-work-tree"], repo_path, token)
        if not check["success"]:
            return self._fail(steps, f"Nie jest repozytorium git: {repo_path}", token)

        steps.append(_run(["git", "config", "user.name", bot_name], repo_path, token))
        steps.append(_run(["git", "config", "user.email", bot_email], repo_path, token))

        steps.append(_run(["git", "checkout", "-b", branch], repo_path, token))
        if not steps[-1]["success"]:
            return self._fail(steps, f"Nie można utworzyć gałęzi: {branch}", token)

        for f in files:
            steps.append(_run(["git", "add", f], repo_path, token))

        steps.append(_run(["git", "commit", "-m", message], repo_path, token))
        if not steps[-1]["success"]:
            return self._fail(steps, "git commit nieudany — brak zmian do zacommitowania", token)

        hash_result = _run(["git", "rev-parse", "HEAD"], repo_path, token)
        commit_hash = hash_result["output"] if hash_result["success"] else "nieznany"

        # Push z tokenem — tylko jeśli jawnie zezwolono I token istnieje
        pushed = False
        if push and token:
            # Pobierz aktualny URL remote i wstrzyknij token
            remote_result = _run(["git", "remote", "get-url", "origin"], repo_path, token)
            if remote_result["success"]:
                auth_url = _inject_token(remote_result["output"], bot_name, token)
                steps.append(_run(
                    ["git", "push", "-u", auth_url, branch],
                    repo_path, token,
                ))
                pushed = steps[-1]["success"]
            else:
                logger.warning("Brak remote 'origin' — nie można wypchnąć gałęzi")
        elif push and not token:
            logger.warning("push=True ale GIT_BOT_TOKEN nie jest ustawiony — pomijam push")

        committed_files = self._list_committed_files(repo_path, token)

        return {
            "mode": "commit",
            "repo_path": str(repo_path),
            "branch": branch,
            "commit_hash": commit_hash,
            "commit_message": message,
            "files_committed": committed_files,
            "remote_url": None,
            "pushed": pushed,
            "bot_name": bot_name,
            "bot_email": bot_email,
            "steps": steps,
            "summary": (
                f"Commit '{commit_hash[:8]}' na gałęzi '{branch}'. "
                f"{'Wypchnięto na remote.' if pushed else 'Nie wypchnięto (push=False lub brak tokenu).'}"
            ),
            "status": "completed",
        }

    # ------------------------------------------------------------------
    # Pomocnicze
    # ------------------------------------------------------------------

    @staticmethod
    def _list_committed_files(repo_path: Path, token: str) -> list[str]:
        result = _run(["git", "show", "--stat", "--format=", "HEAD"], repo_path, token)
        return [
            line.strip().split(" | ")[0].strip()
            for line in result["output"].splitlines()
            if " | " in line
        ]

    @staticmethod
    def _fail(steps: list[dict], reason: str, token: str = "") -> dict:
        last_output = _mask(steps[-1]["output"], token) if steps else ""
        return {
            "mode": "unknown",
            "repo_path": "",
            "branch": "",
            "commit_hash": "brak",
            "commit_message": "",
            "files_committed": [],
            "remote_url": None,
            "pushed": False,
            "steps": steps,
            "summary": f"Błąd: {reason}. Ostatni output: {last_output}",
            "status": "failed",
        }
