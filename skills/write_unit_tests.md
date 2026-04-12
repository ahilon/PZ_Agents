# Skill: Napisz unit testy

## Kiedy używać
Gdy chcesz pokryć testami jednostkowymi konkretny moduł, klasę lub funkcję.

## Zasady

### Framework i wersje
- Używaj **pytest** (nie unittest)
- Wymagana wersja: `pytest>=8.0`, `pytest-asyncio>=1.0`
- Dla testów asynchronicznych: `@pytest.mark.asyncio` + `@pytest_asyncio.fixture`
- Mocki: `from unittest.mock import AsyncMock, MagicMock, patch`

### Struktura pliku testowego
```python
"""Testy jednostkowe dla <moduł>."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from src.<moduł> import <Klasa>


@pytest_asyncio.fixture
async def <nazwa_fixture>():
    """Opis fixture."""
    # setup
    yield obiekt
    # teardown (opcjonalnie)


class Test<Klasa>:
    """Grupuj testy powiązane z jedną klasą."""

    @pytest.mark.asyncio
    async def test_<co_testujemy>_<oczekiwany_wynik>(self, fixture):
        ...
```

### Nazewnictwo testów
Format: `test_<co_testujemy>_<warunek>_<oczekiwany_wynik>`

Przykłady:
- `test_execute_success_returns_response`
- `test_execute_timeout_returns_error`
- `test_parse_empty_input_raises_value_error`

### Mocki — kiedy i jak
- Mockuj **zewnętrzne zależności**: API, bazy danych, system plików, subprocess
- **Nie mockuj** kodu wewnętrznego, który testujesz
- Używaj `patch` jako context manager (nie dekorator przy metodach async klasy):

```python
async def test_run_success(self):
    with patch("src.agents.git_agent.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        ...
```

- Dla atrybutów instancji (np. `_llm`) — **przypisuj bezpośrednio na instancji**, nie używaj `@patch.object` na klasie:
```python
async def test_call_llm_with_client(self, agent):
    mock_llm = MagicMock()
    mock_llm.chat.completions.create = AsyncMock(return_value=...)
    agent._llm = mock_llm   # przypisanie na instancji, nie patch.object
    ...
```

- Dla patchowania modułowych stałych (`DEFAULT_TIMEOUT` itp.) używaj ścieżki modułu:
```python
with patch("src.agents.base_agent.asyncio.wait_for", side_effect=asyncio.TimeoutError):
    ...
```

- Nigdy nie używaj `AgentState` zamiast `AgentType` — to dwa różne Enumy:
  - `AgentType` — typ agenta (CODE_GENERATOR, GIT, itp.) — używaj w `AgentConfig` i `Task`
  - `AgentState` — stan wykonania (IDLE, RUNNING, itp.) — używaj w asercjach stanu

### Warunki graniczne — zawsze dodaj
Dla każdej funkcji sprawdź:
- Pusty input (`""`, `[]`, `{}`, `None`)
- Maksymalny input (bardzo długi string, duża lista)
- Nieprawidłowy typ (int zamiast str itp.) — jeśli funkcja tego nie sprawdza, dodaj `pytest.raises`
- Wartości graniczne liczbowe (0, -1, MAX_INT)
- Timeout / wolna odpowiedź zewnętrznego serwisu

```python
@pytest.mark.parametrize("bad_input", [None, "", [], {}])
async def test_process_invalid_input_raises(self, bad_input):
    with pytest.raises((ValueError, TypeError)):
        await agent.process(bad_input)
```

### Asercje
- Jedna asercja logiczna na test (możliwe wiele `assert` jeśli dotyczą tego samego faktu)
- Preferuj `assert result == expected` nad `assert result` (bardziej czytelne błędy)
- Używaj `pytest.approx` dla floatów: `assert score == pytest.approx(9.5, abs=0.1)`

### Co NIE należy do unit testów
- Prawdziwe wywołania API (to integration testy)
- Prawdziwe operacje na dysku (użyj `tmp_path` fixture pytest)
- Prawdziwe wywołania git (zamockuj `subprocess.run`)

## Przykład kompletnego pliku

```python
"""Testy jednostkowe dla BaseAgent."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from src.agents.base_agent import BaseAgent
from src.models.agent import AgentConfig, AgentState, AgentType, Task


class ConcreteAgent(BaseAgent):
    """Minimalna implementacja do testów."""
    async def _process_task(self, task):
        return {"done": True}


@pytest_asyncio.fixture
async def agent():
    config = AgentConfig(
        name="Test Agent",
        agent_type=AgentType.CUSTOM,
        description="Test",
    )
    return ConcreteAgent(config)


class TestBaseAgentExecution:

    @pytest.mark.asyncio
    async def test_execute_success_returns_response(self, agent, sample_task):
        response = await agent.execute(sample_task)
        assert response.success is True
        assert response.result == {"done": True}

    @pytest.mark.asyncio
    async def test_execute_sets_state_idle_after_completion(self, agent, sample_task):
        await agent.execute(sample_task)
        assert agent.state == AgentState.IDLE

    @pytest.mark.asyncio
    async def test_execute_timeout_returns_error(self, agent, sample_task):
        with patch("src.agents.base_agent.DEFAULT_TASK_TIMEOUT", 0.001):
            response = await agent.execute(sample_task)
        assert response.success is False
        assert "timeout" in response.error.lower()

    @pytest.mark.asyncio
    async def test_execute_exception_returns_error(self, agent, sample_task):
        agent._process_task = AsyncMock(side_effect=RuntimeError("boom"))
        response = await agent.execute(sample_task)
        assert response.success is False
        assert "boom" in response.error


class TestBaseAgentEdgeCases:

    @pytest.mark.asyncio
    async def test_execute_without_api_key_still_works(self, agent, sample_task):
        agent._llm = None
        response = await agent.execute(sample_task)
        assert response.success is True  # _process_task nie woła LLM

    @pytest.mark.asyncio
    async def test_call_llm_without_client_returns_empty(self, agent):
        agent._llm = None
        result = await agent._call_llm("test", response_json=False)
        assert result == ""
```

## Uruchamianie

```bash
poetry run pytest tests/ -v                    # wszystkie testy
poetry run pytest tests/test_foo.py -v         # konkretny plik
poetry run pytest tests/ -k "test_timeout"     # po nazwie
poetry run pytest tests/ --tb=short            # krótszy traceback
```
