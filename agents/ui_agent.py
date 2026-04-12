"""UI Agent — generuje interfejs graficzny aplikacji (Streamlit / FastAPI / Gradio)."""
import logging
from pathlib import Path
from typing import Any

from agents.base_agent import BaseAgent
from src.models.agent import Task

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Jesteś ekspertem od budowania interfejsów użytkownika w Pythonie.

## Obsługiwane frameworki

### Streamlit — dashboardy, narzędzia AI, prototypy
- Używaj st.session_state do stanu, st.sidebar do nawigacji, st.spinner() przy długich operacjach
- Nie używaj asyncio bezpośrednio — Streamlit ma własny event loop

### FastAPI + Jinja2 — REST API z frontendem
- Rozdziel router/logikę/szablony, Pydantic do walidacji, szablony w templates/

### Gradio — interfejsy ML/AI
- gr.Blocks() dla złożonych layoutów, gr.Interface() dla prostych funkcji

## Zasady
- Kod kompletny, gotowy do uruchomienia
- Interfejs w języku polskim
- Obsługa błędów przy wywołaniach zewnętrznych
- Klucze API tylko przez os.getenv()

## Format odpowiedzi
Zwróć WYŁĄCZNIE kod Pythona — bez wstępów i markdown.
"""

_FRAMEWORK_META = {
    "streamlit": {
        "install": "poetry add streamlit",
        "run": "poetry run streamlit run app.py",
        "default_output": "app.py",
        "notes": (
            "Używaj st.sidebar dla nawigacji. Dane przechowuj w st.session_state. "
            "Używaj st.spinner() przy długich operacjach. "
            "Nie blokuj event loop — operacje async owijaj w asyncio.run()."
        ),
    },
    "fastapi": {
        "install": "poetry add fastapi uvicorn jinja2 python-multipart",
        "run": "poetry run uvicorn app.main:app --reload",
        "default_output": "app/main.py",
        "notes": (
            "Twórz router w osobnym pliku. Szablony HTML w templates/. "
            "Statyczne pliki w static/. Używaj Pydantic do walidacji requestów."
        ),
    },
    "gradio": {
        "install": "poetry add gradio",
        "run": "poetry run python app.py",
        "default_output": "app.py",
        "notes": "Używaj gr.Blocks() dla złożonych layoutów. Dla prostych — gr.Interface().",
    },
}


def _strip_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        text = "\n".join(lines[1:end])
    return text


class UIAgent(BaseAgent):
    """Generuje interfejs użytkownika — Streamlit, FastAPI lub Gradio."""

    async def _process_task(self, task: Task) -> Any:
        p = task.parameters
        framework = p.get("framework", "streamlit").lower()

        if framework not in _FRAMEWORK_META:
            return {
                "status": "failed",
                "summary": f"Nieznany framework: '{framework}'. Dostępne: {', '.join(_FRAMEWORK_META)}",
            }

        meta = _FRAMEWORK_META[framework]
        backend_code = p.get("target_code", "")
        if not backend_code and p.get("target_file"):
            target = Path(p["target_file"])
            if target.exists():
                backend_code = target.read_text(encoding="utf-8")
            else:
                return {"status": "failed", "summary": f"Plik nie istnieje: {target}"}

        if not self._llm:
            return {"status": "failed", "summary": "Brak OPENAI_API_KEY."}

        prompt = self._build_prompt(
            framework, meta,
            p.get("description", task.description or ""),
            backend_code,
            p.get("components", []),
        )
        code = _strip_fence(await self._call_llm(prompt, response_json=False))

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
            "summary": f"UI ({framework}) → {output_file}. Uruchom: {meta['run']}",
        }

    def _build_prompt(self, framework: str, meta: dict, description: str,
                      backend_code: str, components: list) -> str:
        parts = [
            f"Wygeneruj kompletny interfejs użytkownika używając **{framework}**.",
            "", f"## Wskazówki dla {framework}", meta["notes"],
            "", "## Wymagania", description,
        ]
        if components:
            parts += ["", "## Komponenty", *[f"- {c}" for c in components]]
        if backend_code:
            parts += ["", "## Kod backendu", f"```python\n{backend_code[:5000]}\n```"]
        parts += [
            "", "## Zasady",
            "- Zwróć TYLKO kod Pythona",
            "- Kod kompletny i gotowy do uruchomienia",
            "- Interfejs w języku polskim",
        ]
        return "\n".join(parts)
