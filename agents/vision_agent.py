"""Vision Agent — analiza obrazów z przepisami przez OpenAI Vision (GPT-4o)."""
import base64
import logging
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import AsyncOpenAI

from agents.base_agent import BaseAgent
from src.models.agent import Task

load_dotenv()

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Jesteś ekspertem od analizy przepisów kulinarnych z obrazów.

## Twoja rola
Otrzymujesz obraz (zdjęcie, skan) z przepisem kulinarnym i wydobywasz z niego
ustrukturyzowane dane w formacie JSON.

## Zasady ekstrakcji

### Składniki
- Zawsze podawaj ilość w gramach (przelicz jeśli trzeba)
- Jeśli podana jest ilość sztuk — podaj obie: `"1 szt (75g)"`
- Jeśli gram nie ma — szacuj na podstawie typowych wartości

### Kalorie i makro
- Wydobądź: kalorie, białko (g), węglowodany (g), tłuszcze (g), cukry (g)
- Jeśli są dwie wersje (kobieta/mężczyzna) — zapisz obie osobno
- Jeśli brak danych odżywczych — zwróć null dla tych pól

### Instrukcja
- Usuń wszelkie opinie, emocje, dygresje autora
- Język rzeczowy, bezosobowy ("Pokrój", "Dodaj", nie "Możesz dodać")
- Jeśli coś trzeba przygotować dzień wcześniej — wyodrębnij do `important_notes`

### Zdjęcie posiłku
- Jeśli obraz zawiera zdjęcie gotowego dania (nie tylko tekst) — ustaw `has_food_photo: true`

## Format odpowiedzi (JSON)
```json
{
  "dish_name": "Nazwa potrawy",
  "has_food_photo": false,
  "has_gender_variants": false,
  "important_notes": ["nota przed przygotowaniem"],
  "ingredients": [
    {"name": "składnik", "amount": "100g"},
    {"name": "ogórek", "amount": "1 szt (75g)"}
  ],
  "nutrition": {
    "calories": 350,
    "protein_g": 25.0,
    "carbs_g": 30.0,
    "fat_g": 12.0,
    "sugar_g": 5.0
  },
  "nutrition_female": null,
  "nutrition_male": null,
  "instructions": [
    "Krok 1: ...",
    "Krok 2: ..."
  ]
}
```
Jeśli `has_gender_variants` to true — wypełnij `nutrition_female` i `nutrition_male`
zamiast (lub obok) głównego `nutrition`.
"""


def _encode_image(path: Path) -> str:
    """Konwertuje plik obrazu do base64."""
    return base64.b64encode(path.read_bytes()).decode("utf-8")


def _mime_type(path: Path) -> str:
    ext = path.suffix.lower()
    return {"jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
            ".webp": "image/webp"}.get(ext, "image/jpeg")


class VisionAgent(BaseAgent):
    """
    Analizuje obraz z przepisem i zwraca ustrukturyzowane dane JSON.

    Parametry task:
      image_path   (str)        — ścieżka do pliku obrazu (PNG/JPG/WEBP)
      image_base64 (str)        — obraz jako base64 (alternatywa dla image_path)
      mime_type    (str)        — "image/jpeg" | "image/png" (domyślnie: z rozszerzenia)
      model        (str)        — model OpenAI (domyślnie: gpt-4o)

    Zwraca:
      {
        "dish_name": "...",
        "ingredients": [...],
        "nutrition": {...},
        "instructions": [...],
        "important_notes": [...],
        "has_food_photo": bool,
        "has_gender_variants": bool,
        "status": "completed"
      }
    """

    async def _process_task(self, task: Task) -> Any:
        p = task.parameters
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            return {"status": "failed", "summary": "Brak OPENAI_API_KEY."}

        # Załaduj obraz
        image_b64 = p.get("image_base64", "")
        mime = p.get("mime_type", "image/jpeg")

        if not image_b64 and p.get("image_path"):
            img_path = Path(p["image_path"])
            if not img_path.exists():
                return {"status": "failed", "summary": f"Plik nie istnieje: {img_path}"}
            image_b64 = _encode_image(img_path)
            mime = _mime_type(img_path)

        if not image_b64:
            return {"status": "failed", "summary": "Brak obrazu — podaj image_path lub image_base64."}

        model = p.get("model", "gpt-4o")
        client = AsyncOpenAI(api_key=api_key)

        logger.info(f"VisionAgent: analizuję obraz modelem {model}...")

        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{mime};base64,{image_b64}"},
                            },
                            {
                                "type": "text",
                                "text": "Przeanalizuj ten przepis i zwróć dane w formacie JSON.",
                            },
                        ],
                    },
                ],
                response_format={"type": "json_object"},
                max_tokens=2000,
                temperature=0.1,
            )
        except Exception as e:
            return {"status": "failed", "summary": f"Błąd API OpenAI: {e}"}

        import json
        raw = response.choices[0].message.content or "{}"
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return {"status": "failed", "summary": f"Błąd parsowania JSON: {raw[:200]}"}

        data["status"] = "completed"
        data["summary"] = f"Wyodrębniono przepis: {data.get('dish_name', '?')} ({len(data.get('ingredients', []))} składników, {len(data.get('instructions', []))} kroków)"
        logger.info(f"VisionAgent: {data['summary']}")
        return data
