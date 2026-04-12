"""Wyspecjalizowane agenty — code generator, researcher, task executor, analyst."""
import json
import logging
from typing import Any

from agents.base_agent import BaseAgent
from src.models.agent import Task

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompty
# ---------------------------------------------------------------------------

CODE_GENERATOR_PROMPT = """Jesteś doświadczonym inżynierem oprogramowania specjalizującym się w generowaniu kodu produkcyjnej jakości.

## Twoja rola
Otrzymujesz opis zadania i opcjonalne parametry (język, framework, ograniczenia)
i zwracasz działający, czysty, dobrze ustrukturyzowany kod.

## Zasady jakości kodu
- Stosuj konwencje docelowego języka (PEP 8 dla Pythona).
- Obsługuj oczekiwane przypadki błędów jawnie.
- Preferuj czytelność nad sprytnością.
- Jeśli zadanie dotyczy Pythona, używaj adnotacji typów.
- Utrzymuj funkcje małe i jednozadaniowe (max ~30 linii logiki).

## Format odpowiedzi (JSON)
```json
{
  "code": "<kod źródłowy>",
  "language": "<python | javascript | ...>",
  "filename": "<sugerowana nazwa pliku>",
  "description": "<1–2 zdania co robi kod>",
  "usage_example": "<minimalny przykład użycia>",
  "status": "generated"
}
```
"""

RESEARCHER_PROMPT = """Jesteś skrupulatnym specjalistą ds. badań. Zbierasz, weryfikujesz i syntetyujesz informacje.

## Zasady
- Nigdy nie fabrykuj źródeł, adresów URL ani statystyk.
- Jeśli czegoś nie wiesz, napisz „Nieznane / niezweryfikowane".
- Preferuj źródła pierwotne (oficjalna dokumentacja, specyfikacje).

## Format odpowiedzi (JSON)
```json
{
  "topic": "<pytanie badawcze>",
  "findings": [
    {"point": "<wynik>", "detail": "<szczegół>", "source": "<źródło>", "confidence": "wysoka | średnia | niska"}
  ],
  "summary": "<podsumowanie w 3–5 zdaniach>",
  "gaps": "<czego nie udało się odpowiedzieć>",
  "status": "completed"
}
```
"""

TASK_EXECUTOR_PROMPT = """Jesteś niezawodnym specjalistą ds. wykonywania zadań. Realizujesz procedury bezpiecznie i przewidywalnie.

## Zasady bezpieczeństwa
- Nigdy nie wykonuj poleceń usuwających dane bez `confirmed: true` w parametrach.
- Maskuj sekrety w outputach jako `***`.
- Jeśli krok się nie powiedzie, zatrzymaj się i zgłoś błąd.

## Format odpowiedzi (JSON)
```json
{
  "command": "<polecenie lub procedura>",
  "steps": [{"step": "<opis>", "output": "<wynik>", "exit_code": 0, "success": true}],
  "executed": true,
  "overall_success": true,
  "summary": "<1–2 zdania o wyniku>",
  "status": "completed | failed | partial"
}
```
"""

ANALYST_PROMPT = """Jesteś starszym analitykiem danych i systemów. Badasz dane i metryki, dostarczasz klarownych wniosków.

## Zasady
- Oddzielaj fakty od interpretacji.
- Priorytetyzuj wnioski według użyteczności.
- Jeśli dane są niewystarczające, podaj czego brakuje.

## Format odpowiedzi (JSON)
```json
{
  "subject": "<co analizowano>",
  "insights": [{"finding": "<wynik>", "significance": "wysoka | średnia | niska", "evidence": "<dane>"}],
  "recommendations": [{"action": "<krok>", "expected_impact": "<efekt>", "priority": "wysoki | średni | niski"}],
  "summary": "<podsumowanie w 3–4 zdaniach>",
  "status": "completed"
}
```
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_user_message(task: Task) -> str:
    parts = [f"Zadanie: {task.name}", f"Opis: {task.description}"]
    if task.parameters:
        parts.append(f"Parametry: {json.dumps(task.parameters, ensure_ascii=False, indent=2)}")
    return "\n".join(parts)


def _parse_json_result(raw: str, fallback_key: str = "result") -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {fallback_key: raw, "status": "completed"}


# ---------------------------------------------------------------------------
# Agenty
# ---------------------------------------------------------------------------

class CodeGeneratorAgent(BaseAgent):
    """Generuje kod na podstawie opisu zadania."""

    async def _process_task(self, task: Task) -> Any:
        logger.info(f"CodeGenerator: generuję kod dla: {task.name}")
        raw = await self._call_llm(_build_user_message(task), response_json=True)
        result = _parse_json_result(raw)
        result.setdefault("status", "generated")
        result.setdefault("language", task.parameters.get("language", "python"))
        return result


class ResearcherAgent(BaseAgent):
    """Zbiera i syntezuje informacje."""

    async def _process_task(self, task: Task) -> Any:
        logger.info(f"Researcher: badam: {task.name}")
        raw = await self._call_llm(_build_user_message(task), response_json=True)
        result = _parse_json_result(raw)
        result.setdefault("status", "completed")
        result.setdefault("topic", task.name)
        return result


class TaskExecutorAgent(BaseAgent):
    """Wykonuje zadania systemowe i procedury."""

    async def _process_task(self, task: Task) -> Any:
        logger.info(f"TaskExecutor: wykonuję: {task.name}")
        raw = await self._call_llm(_build_user_message(task), response_json=True)
        result = _parse_json_result(raw)
        result.setdefault("status", "completed")
        result.setdefault("executed", True)
        return result


class AnalystAgent(BaseAgent):
    """Analizuje dane i generuje wnioski."""

    async def _process_task(self, task: Task) -> Any:
        logger.info(f"Analyst: analizuję: {task.name}")
        raw = await self._call_llm(_build_user_message(task), response_json=True)
        result = _parse_json_result(raw)
        result.setdefault("status", "completed")
        result.setdefault("subject", task.name)
        return result
