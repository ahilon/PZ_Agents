"""Skill Agent — wykonuje zadania na podstawie plików skill w katalogu skills/."""
import logging
from pathlib import Path
from typing import Any

from src.agents.base_agent import BaseAgent
from src.models.agent import Task

logger = logging.getLogger(__name__)

SKILLS_DIR = Path(__file__).resolve().parents[2] / "skills"


def _find_skill(name: str) -> Path | None:
    """Znajduje plik skill po nazwie lub aliasie. Ignoruje wielkość liter i myślniki/spacje."""
    normalized = name.lower().replace(" ", "_").replace("-", "_")
    for path in SKILLS_DIR.glob("*.md"):
        if path.stem.lower().replace("-", "_") == normalized:
            return path
    return None


def _list_skills() -> list[str]:
    return sorted(p.stem for p in SKILLS_DIR.glob("*.md"))


class SkillAgent(BaseAgent):
    """
    Agent wykonujący zadania według instrukcji z pliku skill (.md).

    Parametry task:
      skill       (str)        — nazwa skilla, np. "write_unit_tests"
      target_file (str)        — plik źródłowy do przetestowania/przejrzenia
      target_code (str)        — kod źródłowy (alternatywa dla target_file)
      context     (str)        — dodatkowy kontekst (opcjonalny)
      output_file (str)        — gdzie zapisać wynik (opcjonalny)

    Zwraca:
      {
        "skill": "write_unit_tests",
        "output": "<wygenerowany kod / tekst>",
        "output_file": "tests/test_foo.py",   # jeśli podano
        "status": "completed"
      }
    """

    async def _process_task(self, task: Task) -> Any:
        p = task.parameters
        skill_name = p.get("skill", "")

        if not skill_name:
            available = ", ".join(_list_skills())
            return {
                "status": "failed",
                "summary": f"Nie podano nazwy skilla. Dostępne: {available}",
            }

        skill_path = _find_skill(skill_name)
        if not skill_path:
            available = ", ".join(_list_skills())
            return {
                "status": "failed",
                "summary": f"Skill '{skill_name}' nie znaleziony. Dostępne: {available}",
            }

        skill_instructions = skill_path.read_text(encoding="utf-8")
        logger.info(f"SkillAgent: używam skilla '{skill_path.name}'")

        # Załaduj kod docelowy
        target_code = p.get("target_code", "")
        if not target_code and p.get("target_file"):
            target_path = Path(p["target_file"])
            if target_path.exists():
                target_code = target_path.read_text(encoding="utf-8")
            else:
                return {"status": "failed", "summary": f"Plik nie istnieje: {target_path}"}

        context = p.get("context", "")

        prompt = self._build_prompt(skill_instructions, target_code, context, task.description)

        if not self._llm:
            return {
                "status": "failed",
                "summary": "Brak OPENAI_API_KEY — nie można wykonać skilla.",
            }

        output = await self._call_llm(prompt, response_json=False)

        # Usuń ewentualne ```python ``` owinięcie
        output = _strip_fence(output)

        # Zapisz do pliku jeśli podano
        output_file = p.get("output_file")
        if output_file and output:
            out_path = Path(output_file)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(output, encoding="utf-8")
            logger.info(f"SkillAgent: wynik zapisano do {out_path}")

        return {
            "skill": skill_name,
            "output": output,
            "output_file": output_file,
            "status": "completed",
            "summary": f"Skill '{skill_name}' wykonany. Output: {len(output)} znaków.",
        }

    def _build_prompt(
        self,
        skill_instructions: str,
        target_code: str,
        context: str,
        description: str,
    ) -> str:
        parts = [
            "Poniżej znajdziesz instrukcje skilla oraz kod do przetworzenia.",
            "Postępuj DOKŁADNIE według instrukcji skilla.",
            "",
            "# Instrukcje skilla",
            skill_instructions,
        ]

        if target_code:
            parts += ["", "# Kod do przetworzenia", f"```python\n{target_code}\n```"]

        if context:
            parts += ["", "# Dodatkowy kontekst", context]

        if description:
            parts += ["", "# Zadanie", description]

        parts += ["", "Zwróć wynik bezpośrednio — bez wstępów ani wyjaśnień."]
        return "\n".join(parts)


def _strip_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        text = "\n".join(lines[1:end])
    return text
