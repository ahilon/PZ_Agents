# AI-agents

## Przegląd projektu / Project Overview

**PL:**  
Projekt AI-agents to system agentów AI zaprojektowany do automatyzacji zadań i orkiestracji. System składa się z różnych typów agentów, które współpracują, aby realizować zadania takie jak generowanie kodu, badania, analiza danych i zarządzanie repozytoriami Git.

**EN:**  
The AI-agents project is an AI agent system designed for task automation and orchestration. The system consists of various types of agents that work together to perform tasks such as code generation, research, data analysis, and Git repository management.

## Diagram architektury / Architecture Diagram

**PL:**  
Diagram architektury przedstawia interakcje między różnymi komponentami systemu AI-agents, w tym agentami specjalizowanymi i agentem orkiestrującym.

**EN:**  
The architecture diagram illustrates the interactions between different components of the AI-agents system, including specialized agents and the orchestrating agent.

![Architecture Diagram](docs/architecture_diagram.png)

## Typy agentów / Agent Types

**PL:**  
- **OrchestratorAgent**: Zarządza i koordynuje inne agenty.
- **CodeGeneratorAgent**: Specjalizuje się w generowaniu kodu.
- **ResearcherAgent**: Zajmuje się badaniami i zbieraniem informacji.
- **TaskExecutorAgent**: Wykonuje zadania systemowe.
- **AnalystAgent**: Specjalizuje się w analizie danych.

**EN:**  
- **OrchestratorAgent**: Manages and coordinates other agents.
- **CodeGeneratorAgent**: Specializes in code generation.
- **ResearcherAgent**: Focuses on research and information gathering.
- **TaskExecutorAgent**: Executes system tasks.
- **AnalystAgent**: Specializes in data analysis.

## Instalacja / Installation

**PL:**  
Wymagania:
- Python 3.12 lub nowszy

Kroki instalacji:
1. Sklonuj repozytorium:  
   ```bash
   git clone https://github.com/yourusername/ai-agents.git
   cd ai-agents
   ```
2. Zainstaluj zależności:  
   ```bash
   pip install -r requirements.txt
   ```

**EN:**  
Requirements:
- Python 3.12 or newer

Installation steps:
1. Clone the repository:  
   ```bash
   git clone https://github.com/yourusername/ai-agents.git
   cd ai-agents
   ```
2. Install dependencies:  
   ```bash
   pip install -r requirements.txt
   ```

## Uruchamianie projektu / Running the Project

**PL:**  
Aby uruchomić projekt, użyj poniższego polecenia:  
```bash
python run_project.py
```

**EN:**  
To run the project, use the following command:  
```bash
python run_project.py
```

## Uruchamianie testów / Running Tests

**PL:**  
Aby uruchomić testy jednostkowe, użyj:  
```bash
pytest tests/
```

**EN:**  
To run unit tests, use:  
```bash
pytest tests/
```

## Agent dokumentacji / Documentation Agent

**PL:**  
Agent dokumentacji automatycznie generuje i aktualizuje dokumentację projektu, zapewniając, że jest zawsze aktualna z najnowszymi zmianami w kodzie.

**EN:**  
The documentation agent automatically generates and updates the project documentation, ensuring it is always up-to-date with the latest code changes.

## Konfiguracja / Configuration

**PL:**  
Ustawienia konfiguracyjne są przechowywane w pliku `.env`. Przykładowe wartości można znaleźć w `.env.example`.

**EN:**  
Configuration settings are stored in the `.env` file. Example values can be found in `.env.example`.

## Rozszerzanie systemu / Extending the System

**PL:**  
Aby dodać nowego agenta, zaimplementuj nową klasę agenta dziedziczącą po `BaseAgent` i zarejestruj ją w `OrchestratorAgent`.

**EN:**  
To add a new agent, implement a new agent class inheriting from `BaseAgent` and register it with the `OrchestratorAgent`.

## Zależności / Dependencies

**PL:**  
- openai (>=2.31.0,<3.0.0)
- python-dotenv (>=1.2.2,<2.0.0)
- pydantic (>=2.12.5,<3.0.0)
- pydantic-settings (>=2.0.0,<3.0.0)
- langchain (>=1.2.15,<2.0.0)
- requests (>=2.33.1,<3.0.0)

**EN:**  
- openai (>=2.31.0,<3.0.0)
- python-dotenv (>=1.2.2,<2.0.0)
- pydantic (>=2.12.5,<3.0.0)
- pydantic-settings (>=2.0.0,<3.0.0)
- langchain (>=1.2.15,<2.0.0)
- requests (>=2.33.1,<3.0.0)

## Licencja / License

**PL:**  
Projekt jest licencjonowany na zasadach licencji MIT. Szczegóły można znaleźć w pliku LICENSE.

**EN:**  
The project is licensed under the MIT License. Details can be found in the LICENSE file.