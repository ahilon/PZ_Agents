"""Docx Agent — generuje plik Word (.docx) z ustrukturyzowanym przepisem kulinarnym."""
import logging
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


def _cm_to_emu(cm: float) -> int:
    """Konwertuje cm do EMU (English Metric Units) dla obrazów w docx."""
    return int(cm * 914400 / 2.54)


class DocxAgent(BaseAgent):
    """
    Generuje plik .docx z przepisem wg specyfikacji:
    - Format A5, marginesy 15mm
    - Tytuł — wyśrodkowany, pogrubiony
    - Ważne noty przed przygotowaniem (jeśli są)
    - Tabela składników + makroskładniki
    - Instrukcja krok po kroku
    - Zdjęcie 5x5cm na dole, wyśrodkowane (jeśli dostępne)

    Parametry task:
      recipe_data  (dict) — dane z VisionAgent
      output_path  (str)  — ścieżka zapisu pliku (domyślnie: <dish_name>.docx)
      image_path   (str)  — ścieżka do zdjęcia posiłku (opcjonalnie)

    Zwraca:
      {"output_path": "...", "status": "completed"}
    """

    async def _process_task(self, task: Task) -> Any:
        try:
            from docx import Document
            from docx.enum.text import WD_ALIGN_PARAGRAPH
            from docx.oxml import OxmlElement
            from docx.oxml.ns import qn
            from docx.shared import Cm, Pt, RGBColor
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
        title_para = doc.add_paragraph()
        title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = title_para.add_run(dish_name.upper())
        run.bold = True
        run.font.size = Pt(14)

        doc.add_paragraph()  # odstęp

        # --- Ważne noty ---
        notes = recipe.get("important_notes", [])
        if notes:
            note_heading = doc.add_paragraph()
            note_heading.add_run("Ważne przed przygotowaniem:").bold = True
            for note in notes:
                p_note = doc.add_paragraph(style="List Bullet")
                p_note.add_run(note)
            doc.add_paragraph()

        # --- Tabela składników ---
        has_variants = recipe.get("has_gender_variants", False)
        self._add_ingredients_table(doc, recipe, has_variants)
        doc.add_paragraph()

        # --- Instrukcja ---
        instructions = recipe.get("instructions", [])
        if instructions:
            inst_heading = doc.add_paragraph()
            inst_heading.add_run("Przygotowanie:").bold = True
            for i, step in enumerate(instructions, 1):
                step_text = step
                # Usuń prefix "Krok N:" jeśli VisionAgent go dodał
                if step_text.lower().startswith(f"krok {i}:"):
                    step_text = step_text.split(":", 1)[-1].strip()
                doc.add_paragraph(f"{i}. {step_text}")

        # --- Zdjęcie ---
        if image_path and image_path.exists() and recipe.get("has_food_photo", False):
            doc.add_paragraph()
            img_para = doc.add_paragraph()
            img_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run_img = img_para.add_run()
            run_img.add_picture(str(image_path), width=Cm(5), height=Cm(5))

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
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn
        from docx.shared import Pt

        section = doc.sections[0]
        section.page_width  = _A5_W
        section.page_height = _A5_H
        section.left_margin   = _MARGIN
        section.right_margin  = _MARGIN
        section.top_margin    = _MARGIN
        section.bottom_margin = _MARGIN

        # Domyślna czcionka dokumentu
        style = doc.styles["Normal"]
        style.font.name = "Calibri"
        style.font.size = Pt(10)

    def _add_ingredients_table(self, doc, recipe: dict, has_variants: bool) -> None:
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.oxml.ns import qn
        from docx.shared import Pt, RGBColor

        ingredients = recipe.get("ingredients", [])
        nutrition   = recipe.get("nutrition") or {}
        nutr_f      = recipe.get("nutrition_female") or {}
        nutr_m      = recipe.get("nutrition_male") or {}

        # Nagłówek tabeli
        if has_variants:
            cols = 3
            headers = ["Składnik / Ilość", "Kobieta", "Mężczyzna"]
        else:
            cols = 2
            headers = ["Składnik", "Ilość"]

        table = doc.add_table(rows=1, cols=cols)
        table.style = "Table Grid"

        # Wiersz nagłówkowy
        hdr_cells = table.rows[0].cells
        for i, h in enumerate(headers):
            hdr_cells[i].text = h
            run = hdr_cells[i].paragraphs[0].runs[0]
            run.bold = True
            hdr_cells[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

        # Składniki
        for ing in ingredients:
            row = table.add_row().cells
            row[0].text = ing.get("name", "")
            if has_variants:
                row[1].text = ing.get("amount_female", ing.get("amount", ""))
                row[2].text = ing.get("amount_male",   ing.get("amount", ""))
            else:
                row[1].text = ing.get("amount", "")

        # Separator + makroskładniki
        def _add_nutrition_rows(table, nutrition: dict, has_variants: bool,
                                nutr_f: dict, nutr_m: dict) -> None:
            fields = [
                ("Kalorie (kcal)", "calories"),
                ("Białko (g)",     "protein_g"),
                ("Węglowodany (g)", "carbs_g"),
                ("Tłuszcze (g)",   "fat_g"),
                ("Cukry (g)",      "sugar_g"),
            ]
            sep = table.add_row().cells
            sep[0].text = "— Wartości odżywcze —"
            p = sep[0].paragraphs[0]
            p.runs[0].bold = True
            # Scal komórki wiersza separatora
            if len(sep) > 1:
                sep[0].merge(sep[-1])

            for label, key in fields:
                row = table.add_row().cells
                row[0].text = label
                if has_variants:
                    row[1].text = str(nutr_f.get(key, "—"))
                    row[2].text = str(nutr_m.get(key, "—"))
                else:
                    row[1].text = str(nutrition.get(key, "—"))

        if nutrition or (nutr_f and nutr_m):
            _add_nutrition_rows(table, nutrition, has_variants, nutr_f, nutr_m)
