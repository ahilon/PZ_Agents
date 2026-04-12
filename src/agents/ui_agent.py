"""UI Agent — generuje interfejs graficzny aplikacji (Streamlit / FastAPI+Jinja2)."""
import logging
from pathlib import Path
from typing import Any

from src.agents.base_agent import BaseAgent
from src.models.agent import Task

logger = logging.getLogger(__name__)


class UIAgent(BaseAgent):
    """
    Agent generujący interfejs użytkownika dla projektów Python.

    Obsługiwane frameworki:
      - streamlit  — szybkie dashboardy i narzędzia wewnętrzne (domyślny)
      - fastapi    — REST API + HTML/Jinja2 frontend
      - gradio     — interfejsy do modeli ML/AI

    Parametry task:
      framework     (str)        — "streamlit" | "fastapi" | "gradio" (domyślnie: streamlit)
      description   (str)        — opis co UI ma robić / jakie funkcje pokazywać
      target_file   (str)        — plik z logiką backendu do owinięcia w UI (opcjonalny)
      target_code   (str)        — kod backendu jako string (alternatywa dla target_file)
      output_file   (str)        — gdzie zapisać wygenerowany UI (opcjonalny)
      components    (list[str])  — lista komponentów do wygenerowania, np. ["form", "table", "chart"]
      repo_path     (str)        — ścieżka do projektu (domyślnie: ".")

    Zwraca:
      {
        "framework": "streamlit",
        "output_file": "app.py",
        "output": "<wygenerowany kod>",
        "install_cmd": "poetry add streamlit",
        "run_cmd": "poetry run streamlit run app.py",
        "status": "completed"
      }
    """

    # Instrukcje startowe i komendy per framework
    _FRAMEWORK_META = {
        "streamlit": {
            "install": "poetry add streamlit",
            "run": "poetry run streamlit run app.py",
            "default_output": "app.py",
            "notes": (
                "Używaj st.sidebar dla nawigacji. "
                "Dane przechowuj w st.session_state. "
                "Używaj st.spinner() przy długich operacjach. "
                "Nie blokuj event loop — operacje async owijaj w asyncio.run()."
            ),
        },
        "fastapi": {
            "install": "poetry add fastapi uvicorn jinja2 python-multipart",
            "run": "poetry run uvicorn app.main:app --reload",
            "default_output": "app/main.py",
            "notes": (
                "Twórz router w osobnym pliku. "
                "Szablony HTML umieszczaj w templates/. "
                "Statyczne pliki (CSS/JS) w static/. "
                "Używaj Pydantic do walidacji requestów."
            ),
        },
        "gradio": {
            "install": "poetry add gradio",
            "run": "poetry run python app.py",
            "default_output": "app.py",
            "notes": (
                "Używaj gr.Blocks() dla złożonych layoutów. "
                "Dla prostych funkcji wystarczy gr.Interface(). "
                "Długie operacje owijaj w gr.Progress()."
            ),
        },
    }

    async def _process_task(self, task: Task) -> Any:
        p = task.parameters
        framework = p.get("framework", "streamlit").lower()

        if framework not in self._FRAMEWORK_META:
            return {
                "status": "failed",
                "summary": f"Nieznany framework: '{framework}'. Dostępne: {', '.join(self._FRAMEWORK_META)}",
            }

        meta = self._FRAMEWORK_META[framework]

        # Załaduj kod backendu jeśli podano
        backend_code = p.get("target_code", "")
        if not backend_code and p.get("target_file"):
            target = Path(p["target_file"])
            if target.exists():
                backend_code = target.read_text(encoding="utf-8")
            else:
                return {"status": "failed", "summary": f"Plik nie istnieje: {target}"}

        components = p.get("components", [])
        description = p.get("description", task.description or "")

        if not self._llm:
            return {"status": "failed", "summary": "Brak OPENAI_API_KEY."}

        prompt = self._build_prompt(framework, meta, description, backend_code, components)
        code = await self._call_llm(prompt, response_json=False)
        code = _strip_fence(code)

        output_file = p.get("output_file", meta["default_output"])
        if code:
            out_path = Path(p.get("repo_path", ".")) / output_file
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(code, encoding="utf-8")
            logger.info(f"UIAgent: zapisano {out_path}")

        return {
            "framework": framework,
            "output_file": output_file,
            "output": code,
            "install_cmd": meta["install"],
            "run_cmd": meta["run"],
            "status": "completed",
            "summary": (
                f"UI ({framework}) wygenerowany → {output_file}. "
                f"Uruchom: {meta['run']}"
            ),
        }

    def _build_prompt(
        self,
        framework: str,
        meta: dict,
        description: str,
        backend_code: str,
        components: list,
    ) -> str:
        parts = [
            f"Wygeneruj kompletny interfejs użytkownika używając frameworka **{framework}**.",
            "",
            f"## Wskazówki dla {framework}",
            meta["notes"],
            "",
            "## Wymagania",
            description,
        ]

        if components:
            parts += ["", "## Komponenty do wygenerowania", *[f"- {c}" for c in components]]

        if backend_code:
            parts += [
                "",
                "## Kod backendu — opakuj go w UI",
                f"```python\n{backend_code[:5000]}\n```",
            ]

        parts += [
            "",
            "## Zasady",
            "- Zwróć TYLKO kod Pythona — bez wyjaśnień, bez markdown",
            "- Kod musi być kompletny i gotowy do uruchomienia",
            "- Dodaj obsługę błędów (try/except przy wywołaniach zewnętrznych)",
            "- Interfejs musi być w języku polskim",
        ]

        return "\n".join(parts)


def _strip_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        text = "\n".join(lines[1:end])
    return text
