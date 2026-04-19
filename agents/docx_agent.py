"""Docx Agent — generuje plik Word (.docx) z ustrukturyzowanym przepisem kulinarnym."""
import logging
import re
from pathlib import Path
from typing import Any

from agents.base_agent import BaseAgent
from src.models.agent import Task

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Jesteś agentem generującym dokumenty Word z przepisami kulinarnymi.
Tworzysz estetyczne, jednolite pliki .docx na podstawie ustrukturyzowanych danych przepisu.
Dbasz o spójny format, czytelność i profesjonalny wygląd.
"""

# Wymiary strony A5 w twipach (1 cm = 567 twipów)
_A5_W = 8391   # 148 mm
_A5_H = 11906  # 210 mm
_MARGIN = 851  # 15 mm

_FONT_NAME = "Arial"
_FONT_SIZE_PT = 6


def _style_run(run, bold: bool = False) -> None:
    from docx.shared import Pt
    run.font.name = _FONT_NAME
    run.font.size = Pt(_FONT_SIZE_PT)
    run.bold = bold


def _add_centered(doc, text: str, bold: bool = False):
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    para = doc.add_paragraph()
    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = para.add_run(text)
    _style_run(run, bold=bold)
    return para


def _sum_amounts(amount_f: str, amount_m: str) -> str:
    """Próbuje zsumować ilości w gramach z dwóch wartości (K i M)."""
    def extract(s: str):
        m = re.search(r"(\d+(?:[.,]\d+)?)\s*g", s)
        if m:
            return float(m.group(1).replace(",", "."))
        m = re.match(r"^\s*(\d+(?:[.,]\d+)?)\s*$", s)
        if m:
            return float(m.group(1).replace(",", "."))
        return None

    f, m = extract(amount_f), extract(amount_m)
    if f is not None and m is not None:
        return f"{f + m:g}g"
    return ""


class DocxAgent(BaseAgent):
    """
    Generuje plik .docx z przepisem wg specyfikacji:
    - Format A5, marginesy 15mm
    - Czcionka Arial 6pt, wszystko wyśrodkowane
    - Tytuł — wyśrodkowany, pogrubiony
    - Ważne noty przed przygotowaniem (jeśli są)
    - Wiersz z porcjami i czasem (jeśli dostępne)
    - Tabela składników + makroskładniki
      - Wariant K/M: kolumny Składnik | Kobieta | Mężczyzna | Suma
    - Instrukcja krok po kroku, wyśrodkowana
    - Zdjęcie 5x5cm na dole, wyśrodkowane (jeśli dostępne)

    Parametry task:
      recipe_data  (dict) — dane z VisionAgent
      output_path  (str)  — ścieżka zapisu pliku (domyślnie: <dish_name>.docx)
      image_path   (str)  — ścieżka do zdjęcia posiłku (opcjonalnie)

    Zwraca:
      {"output_path": "...", "dish_name": "...", "status": "completed"}
    """

    async def _process_task(self, task: Task) -> Any:
        try:
            from docx import Document
            from docx.enum.text import WD_ALIGN_PARAGRAPH
            from docx.shared import Cm, Pt
        except ImportError:
            return {"status": "failed", "summary": "Brak python-docx. Uruchom: poetry add python-docx"}

        p = task.parameters
        recipe = p.get("recipe_data", {})
        if not recipe:
            return {"status": "failed", "summary": "Brak danych przepisu (recipe_data)."}

        dish_name = recipe.get("dish_name", "Przepis")
        output_path = Path(p.get("output_path", f"{dish_name}.docx"))
        image_path = p.get("image_path")
        if image_path:
            image_path = Path(image_path)

        logger.info(f"DocxAgent: generuję '{dish_name}' → {output_path}")

        doc = Document()
        self._set_page_a5(doc)

        # --- Tytuł ---
        _add_centered(doc, dish_name.upper(), bold=True)
        doc.add_paragraph()

        # --- Ważne noty ---
        notes = recipe.get("important_notes", [])
        if notes:
            _add_centered(doc, "Ważne przed przygotowaniem:", bold=True)
            for note in notes:
                _add_centered(doc, f"• {note}")
            doc.add_paragraph()

        # --- Porcje i czas ---
        self._add_meta_row(doc, recipe)

        # --- Tabela składników ---
        has_variants = recipe.get("has_gender_variants", False)
        self._add_ingredients_table(doc, recipe, has_variants)
        doc.add_paragraph()

        # --- Instrukcja ---
        instructions = recipe.get("instructions", [])
        if instructions:
            _add_centered(doc, "Przygotowanie:", bold=True)
            for i, step in enumerate(instructions, 1):
                step_text = step
                if step_text.lower().startswith(f"krok {i}:"):
                    step_text = step_text.split(":", 1)[-1].strip()
                _add_centered(doc, f"{i}. {step_text}")

        # --- Zdjęcie ---
        if image_path and image_path.exists() and recipe.get("has_food_photo", False):
            doc.add_paragraph()
            img_para = doc.add_paragraph()
            img_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            img_para.add_run().add_picture(str(image_path), width=Cm(5), height=Cm(5))

        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(output_path))

        logger.info(f"DocxAgent: zapisano {output_path}")
        return {
            "output_path": str(output_path),
            "dish_name": dish_name,
            "status": "completed",
            "summary": f"Plik '{output_path.name}' wygenerowany.",
        }

    def _set_page_a5(self, doc) -> None:
        from docx.shared import Pt

        section = doc.sections[0]
        section.page_width    = _A5_W
        section.page_height   = _A5_H
        section.left_margin   = _MARGIN
        section.right_margin  = _MARGIN
        section.top_margin    = _MARGIN
        section.bottom_margin = _MARGIN

        style = doc.styles["Normal"]
        style.font.name = _FONT_NAME
        style.font.size = Pt(_FONT_SIZE_PT)

    def _add_meta_row(self, doc, recipe: dict) -> None:
        """Wiersz z porcjami i czasem, jeśli dane są dostępne."""
        parts = []
        if recipe.get("servings"):
            parts.append(f"Porcje: {recipe['servings']}")
        if recipe.get("servings_to_make"):
            parts.append(f"Do przygotowania: {recipe['servings_to_make']} porcji")
        if recipe.get("prep_time"):
            parts.append(f"Przygotowanie: {recipe['prep_time']}")
        if recipe.get("cook_time"):
            parts.append(f"Gotowanie: {recipe['cook_time']}")
        if recipe.get("total_time"):
            parts.append(f"Łączny czas: {recipe['total_time']}")

        if parts:
            _add_centered(doc, "  |  ".join(parts))
            doc.add_paragraph()

    def _add_ingredients_table(self, doc, recipe: dict, has_variants: bool) -> None:
        from docx.enum.text import WD_ALIGN_PARAGRAPH

        ingredients = recipe.get("ingredients", [])
        nutrition   = recipe.get("nutrition") or {}
        nutr_f      = recipe.get("nutrition_female") or {}
        nutr_m      = recipe.get("nutrition_male") or {}

        if has_variants:
            headers = ["Składnik", "Kobieta", "Mężczyzna", "Suma"]
        else:
            headers = ["Składnik", "Ilość"]

        table = doc.add_table(rows=1, cols=len(headers))
        table.style = "Table Grid"

        # Nagłówek
        for i, h in enumerate(table.rows[0].cells):
            h.text = headers[i]
            h.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
            _style_run(h.paragraphs[0].runs[0], bold=True)

        # Składniki
        for ing in ingredients:
            cells = table.add_row().cells
            amount_f = ing.get("amount_female", ing.get("amount", ""))
            amount_m = ing.get("amount_male",   ing.get("amount", ""))

            cells[0].text = ing.get("name", "")
            if has_variants:
                cells[1].text = amount_f
                cells[2].text = amount_m
                cells[3].text = _sum_amounts(amount_f, amount_m)
            else:
                cells[1].text = ing.get("amount", "")

            for cell in cells:
                cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
                for run in cell.paragraphs[0].runs:
                    _style_run(run)

        # Makroskładniki
        if nutrition or (nutr_f and nutr_m):
            self._add_nutrition_rows(table, nutrition, has_variants, nutr_f, nutr_m)

    def _add_nutrition_rows(self, table, nutrition: dict, has_variants: bool,
                            nutr_f: dict, nutr_m: dict) -> None:
        from docx.enum.text import WD_ALIGN_PARAGRAPH

        fields = [
            ("Kalorie (kcal)",  "calories"),
            ("Białko (g)",      "protein_g"),
            ("Węglowodany (g)", "carbs_g"),
            ("Tłuszcze (g)",    "fat_g"),
            ("Cukry (g)",       "sugar_g"),
        ]

        # Wiersz separatora — scalony
        sep = table.add_row().cells
        sep[0].text = "— Wartości odżywcze —"
        sep[0].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        _style_run(sep[0].paragraphs[0].runs[0], bold=True)
        if len(sep) > 1:
            sep[0].merge(sep[-1])

        for label, key in fields:
            cells = table.add_row().cells
            cells[0].text = label
            if has_variants:
                val_f = nutr_f.get(key, "—")
                val_m = nutr_m.get(key, "—")
                cells[1].text = str(val_f)
                cells[2].text = str(val_m)
                try:
                    cells[3].text = str(round(float(val_f) + float(val_m), 1))
                except (TypeError, ValueError):
                    cells[3].text = "—"
            else:
                cells[1].text = str(nutrition.get(key, "—"))

            for cell in cells:
                cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
                for run in cell.paragraphs[0].runs:
                    _style_run(run)
