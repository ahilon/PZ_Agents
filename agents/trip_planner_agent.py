"""Trip Planner Agent — generuje plan podróży w formacie .docx na podstawie pliku Markdown."""
import json
import logging
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from dotenv import load_dotenv
from openai import AsyncOpenAI

from agents.base_agent import BaseAgent
from src.models.agent import Task

load_dotenv()

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Jesteś ekspertem od planowania podróży.

## Twoja rola
Otrzymujesz opis wycieczki w formacie Markdown i generujesz szczegółowy, zoptymalizowany plan podróży w formacie JSON.

## Zasady planowania

### Transport i noclegi
- Przepisz dane dokładnie z opisu
- Dla każdej lokalizacji wygeneruj zapytanie do Google Maps (pole `maps_query`)
- Jeśli koszt podany w walucie innej niż PLN — dodaj orientacyjne przeliczenie na PLN (użyj aktualnej wiedzy o kursach)

### Plan dnia — optymalizacja trasy
- Atrakcje P1 zawsze wchodzą do planu (obowiązkowe)
- Atrakcje P2 dodajesz jeśli realistycznie zmieszczą się czasowo po P1 (zakładaj ~8-10h aktywności dziennie)
- Atrakcje P3 umieszczasz jako sugestie "po drodze" między krokami — NIE jako osobne punkty planu
- Układaj atrakcje w kolejności geograficznie optymalnej (minimalizuj czas transportu)
- Dla każdej pary kolejnych atrakcji podaj: sposób transportu (pieszo / metro / autobus / taxi), szacowany czas przejazdu

### Szacowanie czasów
- Muzea duże (Luwr, Prado): 2-3h
- Muzea małe: 1-1.5h
- Kościoły/katedry: 0.5-1h
- Parki, ogrody: 1-2h
- Dzielnice/spacery: 1-2h
- Plaże: 2-3h
- Zamki/forty: 1.5-2h
- Dodaj 15-30 min na dojście i orientację przy każdej atrakcji

### Koszty wejść
- Podaj orientacyjny koszt wejścia na podstawie swojej wiedzy
- Jeśli wstęp wolny — napisz "bezpłatny"
- Jeśli nie wiesz — napisz "sprawdź na stronie"

### Podsumowanie kosztów
- Zbierz WSZYSTKIE koszty: transport, noclegi, atrakcje (szacunkowo), budżet dzienny
- Każdy koszt przelicz na PLN (orientacyjnie)
- Oznacz które są już zapłacone

## Format odpowiedzi (JSON)
Zwróć TYLKO JSON, bez żadnego dodatkowego tekstu.

```json
{
  "trip_title": "Wycieczka do Barcelony",
  "dates": "15-20.05.2025",
  "travelers": 2,
  "currency_local": "EUR",
  "eur_to_pln": 4.25,

  "transport": [
    {
      "leg": "Podróż tam",
      "type": "samolot",
      "from": "Warszawa Chopin (WAW)",
      "to": "Barcelona El Prat (BCN)",
      "datetime": "15.05.2025, 06:30",
      "number": "FR1234",
      "cost_amount": 400,
      "cost_currency": "PLN",
      "cost_pln": 400,
      "paid": true,
      "maps_query": "Barcelona El Prat Airport"
    }
  ],

  "accommodation": [
    {
      "name": "Hotel Arts Barcelona",
      "address": "Carrer de la Marina 19-21, Barcelona",
      "checkin": "15.05.2025 od 15:00",
      "checkout": "20.05.2025 do 12:00",
      "nights": 5,
      "cost_amount": 900,
      "cost_currency": "EUR",
      "cost_pln": 3825,
      "paid": false,
      "maps_query": "Hotel Arts Barcelona Carrer de la Marina"
    }
  ],

  "days": [
    {
      "date": "15.05.2025",
      "label": "Dzień 1 — Przybycie i Sagrada Familia",
      "attractions": [
        {
          "name": "Sagrada Familia",
          "priority": 1,
          "address": "Carrer de Mallorca 401, Barcelona",
          "maps_query": "Sagrada Familia Barcelona",
          "estimated_hours": 2.0,
          "entrance_cost": "26 EUR",
          "transport_from_prev": "metro L5 od hotelu, ok. 20 min, ~2.40 EUR",
          "p3_suggestions": [],
          "notes": "Bilety kupić z wyprzedzeniem online"
        }
      ],
      "p2_attractions": [
        {
          "name": "Casa Batlló",
          "maps_query": "Casa Batllo Barcelona",
          "estimated_hours": 1.5,
          "entrance_cost": "35 EUR",
          "reason": "Zostanie ok. 2h po P1 — warto wpaść"
        }
      ],
      "day_summary": "Łącznie ok. 9h aktywności. Szacowany koszt atrakcji: ~55 EUR/os"
    }
  ],

  "costs": [
    {
      "category": "Transport",
      "description": "Lot WAW→BCN, FR1234 (×2 os.)",
      "paid": true,
      "amount": 800,
      "currency": "PLN",
      "amount_pln": 800
    },
    {
      "category": "Nocleg",
      "description": "Hotel Arts Barcelona, 5 nocy",
      "paid": false,
      "amount": 900,
      "currency": "EUR",
      "amount_pln": 3825
    }
  ],

  "total_estimated_pln": 12000
}
```
"""


def _maps_link(query: str) -> str:
    return f"https://www.google.com/maps/search/?api=1&query={quote_plus(query)}"


class TripPlannerAgent(BaseAgent):
    """
    Generuje plan podróży (.docx) na podstawie pliku Markdown z opisem wycieczki.

    Parametry task:
      trip_file    (str) — ścieżka do pliku .md z opisem podróży
      trip_text    (str) — opis podróży jako tekst (alternatywa dla trip_file)
      output_path  (str) — ścieżka wyjściowego .docx (domyślnie: plan_<nazwa>.docx)
      model        (str) — model OpenAI (domyślnie: gpt-4o)

    Zwraca:
      {"output_path": "...", "trip_title": "...", "status": "completed"}
    """

    async def _process_task(self, task: Task) -> Any:
        p = task.parameters
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            return {"status": "failed", "summary": "Brak OPENAI_API_KEY."}

        # Wczytaj opis podróży
        trip_text = p.get("trip_text", "")
        if not trip_text and p.get("trip_file"):
            trip_path = Path(p["trip_file"])
            if not trip_path.exists():
                return {"status": "failed", "summary": f"Plik nie istnieje: {trip_path}"}
            trip_text = trip_path.read_text(encoding="utf-8")

        if not trip_text:
            return {"status": "failed", "summary": "Brak opisu podróży — podaj trip_file lub trip_text."}

        model = p.get("model", "gpt-4o")
        client = AsyncOpenAI(api_key=api_key)

        logger.info("TripPlannerAgent: planuję podróż...")

        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": trip_text},
                ],
                response_format={"type": "json_object"},
                max_tokens=4000,
                temperature=0.2,
            )
        except Exception as e:
            return {"status": "failed", "summary": f"Błąd API OpenAI: {e}"}

        raw = response.choices[0].message.content or "{}"
        try:
            plan = json.loads(raw)
        except json.JSONDecodeError:
            return {"status": "failed", "summary": f"Błąd parsowania JSON: {raw[:200]}"}

        trip_title = plan.get("trip_title", "Plan podróży")
        safe_name = re.sub(r"[^\w\s-]", "", trip_title).strip().replace(" ", "_")
        output_path = Path(p.get("output_path", f"plan_{safe_name}.docx"))

        logger.info(f"TripPlannerAgent: generuję .docx → {output_path}")
        result = self._generate_docx(plan, output_path)

        result["status"] = "completed"
        result["summary"] = f"Plan '{trip_title}' wygenerowany: {output_path}"
        logger.info(f"TripPlannerAgent: {result['summary']}")
        return result

    # ------------------------------------------------------------------
    # DOCX generation
    # ------------------------------------------------------------------

    def _generate_docx(self, plan: dict, output_path: Path) -> dict:
        try:
            from docx import Document
            from docx.enum.text import WD_ALIGN_PARAGRAPH
            from docx.oxml import OxmlElement
            from docx.oxml.ns import qn
            from docx.shared import Cm, Pt, RGBColor
        except ImportError:
            return {"status": "failed", "summary": "Brak python-docx. Uruchom: poetry add python-docx"}

        doc = Document()
        self._setup_document(doc)

        # Strona tytułowa
        self._add_cover(doc, plan)

        # Transport
        transport = plan.get("transport", [])
        if transport:
            self._add_heading(doc, "Transport")
            self._add_transport_table(doc, transport)

        # Noclegi
        accommodation = plan.get("accommodation", [])
        if accommodation:
            self._add_heading(doc, "Noclegi")
            self._add_accommodation_table(doc, accommodation)

        # Plan dnia
        days = plan.get("days", [])
        if days:
            self._add_heading(doc, "Plan dnia")
            for day in days:
                self._add_day_section(doc, day)

        # Koszty
        costs = plan.get("costs", [])
        if costs:
            self._add_heading(doc, "Podsumowanie kosztów")
            self._add_costs_table(doc, costs, plan.get("total_estimated_pln"))

        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(output_path))
        return {"output_path": str(output_path), "trip_title": plan.get("trip_title", "")}

    def _setup_document(self, doc) -> None:
        from docx.shared import Pt

        section = doc.sections[0]
        section.left_margin   = 1440  # 2.54 cm
        section.right_margin  = 1440
        section.top_margin    = 1440
        section.bottom_margin = 1440

        style = doc.styles["Normal"]
        style.font.name = "Calibri"
        style.font.size = Pt(11)

    def _add_cover(self, doc, plan: dict) -> None:
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.shared import Pt

        doc.add_paragraph()
        title_para = doc.add_paragraph()
        title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = title_para.add_run(plan.get("trip_title", "Plan podróży").upper())
        run.bold = True
        run.font.size = Pt(18)

        meta_parts = []
        if plan.get("dates"):
            meta_parts.append(plan["dates"])
        if plan.get("travelers"):
            meta_parts.append(f"{plan['travelers']} os.")

        if meta_parts:
            meta_para = doc.add_paragraph()
            meta_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            meta_run = meta_para.add_run("  •  ".join(meta_parts))
            meta_run.font.size = Pt(12)

        doc.add_paragraph()

    def _add_heading(self, doc, text: str) -> None:
        from docx.shared import Pt, RGBColor

        para = doc.add_paragraph()
        run = para.add_run(text.upper())
        run.bold = True
        run.font.size = Pt(13)
        run.font.color.rgb = RGBColor(0x1F, 0x49, 0x7D)

    def _add_transport_table(self, doc, transport: list) -> None:
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.shared import Pt

        headers = ["Odcinek", "Typ", "Skąd → Dokąd", "Data / Godz.", "Nr", "Koszt", "Zapłacone", "Mapa"]
        table = doc.add_table(rows=1, cols=len(headers))
        table.style = "Table Grid"
        self._fill_header_row(table, headers)

        for leg in transport:
            cells = table.add_row().cells
            paid_str = "✓" if leg.get("paid") else "—"
            cost_str = self._format_cost(leg)
            maps_url = _maps_link(leg.get("maps_query", leg.get("to", "")))

            values = [
                leg.get("leg", ""),
                leg.get("type", ""),
                f"{leg.get('from', '')} → {leg.get('to', '')}",
                leg.get("datetime", ""),
                leg.get("number", ""),
                cost_str,
                paid_str,
                maps_url,
            ]
            for i, val in enumerate(values):
                cells[i].text = val
                cells[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

        doc.add_paragraph()

    def _add_accommodation_table(self, doc, accommodation: list) -> None:
        from docx.enum.text import WD_ALIGN_PARAGRAPH

        headers = ["Nazwa", "Adres", "Check-in", "Check-out", "Noce", "Koszt", "Zapłacone", "Mapa"]
        table = doc.add_table(rows=1, cols=len(headers))
        table.style = "Table Grid"
        self._fill_header_row(table, headers)

        for acc in accommodation:
            cells = table.add_row().cells
            paid_str = "✓" if acc.get("paid") else "—"
            maps_url = _maps_link(acc.get("maps_query", acc.get("name", "")))

            values = [
                acc.get("name", ""),
                acc.get("address", ""),
                acc.get("checkin", ""),
                acc.get("checkout", ""),
                str(acc.get("nights", "")),
                self._format_cost(acc),
                paid_str,
                maps_url,
            ]
            for i, val in enumerate(values):
                cells[i].text = val
                cells[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

        doc.add_paragraph()

    def _add_day_section(self, doc, day: dict) -> None:
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.shared import Pt, RGBColor

        # Nagłówek dnia
        day_para = doc.add_paragraph()
        run = day_para.add_run(f"  {day.get('label', day.get('date', ''))}")
        run.bold = True
        run.font.size = Pt(12)
        run.font.color.rgb = RGBColor(0x2E, 0x74, 0xB5)

        # Tabela atrakcji P1 + P2
        attractions = day.get("attractions", [])
        p2_attractions = day.get("p2_attractions", [])
        all_attractions = attractions + p2_attractions

        if all_attractions:
            headers = ["Prio", "Atrakcja", "Adres", "Czas", "Transport z poprz.", "Koszt wejścia", "Uwagi", "Mapa"]
            table = doc.add_table(rows=1, cols=len(headers))
            table.style = "Table Grid"
            self._fill_header_row(table, headers)

            for attr in attractions:
                self._add_attraction_row(table, attr, priority_label="P1")
                # P3 sugestie jako dodatkowy wiersz
                for p3 in attr.get("p3_suggestions", []):
                    self._add_p3_suggestion_row(table, p3)

            for attr in p2_attractions:
                self._add_attraction_row(table, attr, priority_label="P2")

        # Podsumowanie dnia
        summary = day.get("day_summary", "")
        if summary:
            sum_para = doc.add_paragraph()
            sum_run = sum_para.add_run(f"  → {summary}")
            sum_run.italic = True
            sum_run.font.size = Pt(10)

        doc.add_paragraph()

    def _add_attraction_row(self, table, attr: dict, priority_label: str) -> None:
        from docx.enum.text import WD_ALIGN_PARAGRAPH

        cells = table.add_row().cells
        hours = attr.get("estimated_hours", "")
        time_str = f"{hours}h" if hours else ""
        maps_url = _maps_link(attr.get("maps_query", attr.get("name", "")))
        notes = attr.get("notes", "")

        values = [
            priority_label,
            attr.get("name", ""),
            attr.get("address", ""),
            time_str,
            attr.get("transport_from_prev", ""),
            attr.get("entrance_cost", ""),
            notes,
            maps_url,
        ]
        for i, val in enumerate(values):
            cells[i].text = str(val)
            cells[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

    def _add_p3_suggestion_row(self, table, p3: dict) -> None:
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.shared import RGBColor

        cells = table.add_row().cells
        maps_url = _maps_link(p3.get("maps_query", p3.get("name", "")))
        values = [
            "P3",
            f"↳ {p3.get('name', '')}",
            p3.get("address", ""),
            "",
            p3.get("how_to_get", "po drodze"),
            p3.get("entrance_cost", ""),
            p3.get("notes", ""),
            maps_url,
        ]
        for i, val in enumerate(values):
            cells[i].text = str(val)
            para = cells[i].paragraphs[0]
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for run in para.runs:
                run.font.color.rgb = RGBColor(0x70, 0x70, 0x70)

    def _add_costs_table(self, doc, costs: list, total_pln) -> None:
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.shared import Pt

        has_foreign = any(c.get("currency", "PLN") != "PLN" for c in costs)

        if has_foreign:
            headers = ["Kategoria", "Opis", "Zapłacone", "Kwota", "Waluta", "Kwota (PLN)"]
        else:
            headers = ["Kategoria", "Opis", "Zapłacone", "Kwota (PLN)"]

        table = doc.add_table(rows=1, cols=len(headers))
        table.style = "Table Grid"
        self._fill_header_row(table, headers)

        for cost in costs:
            cells = table.add_row().cells
            paid_str = "✓" if cost.get("paid") else "—"
            currency = cost.get("currency", "PLN")

            if has_foreign:
                values = [
                    cost.get("category", ""),
                    cost.get("description", ""),
                    paid_str,
                    str(cost.get("amount", "")),
                    currency,
                    str(cost.get("amount_pln", "")),
                ]
            else:
                values = [
                    cost.get("category", ""),
                    cost.get("description", ""),
                    paid_str,
                    str(cost.get("amount_pln", cost.get("amount", ""))),
                ]

            for i, val in enumerate(values):
                cells[i].text = val
                cells[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

        # Wiersz sumy
        if total_pln:
            sum_row = table.add_row().cells
            sum_row[0].text = "RAZEM (szacunkowo)"
            sum_row[0].paragraphs[0].runs[0].bold = True
            last_idx = len(headers) - 1
            sum_row[last_idx].text = f"{total_pln:,} PLN".replace(",", " ")
            sum_row[last_idx].paragraphs[0].runs[0].bold = True

        doc.add_paragraph()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _fill_header_row(self, table, headers: list) -> None:
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.shared import RGBColor

        cells = table.rows[0].cells
        for i, h in enumerate(headers):
            cells[i].text = h
            para = cells[i].paragraphs[0]
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = para.runs[0]
            run.bold = True
            run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
            # Ciemne tło nagłówka
            tc = cells[i]._tc
            from docx.oxml import OxmlElement
            from docx.oxml.ns import qn
            tcPr = tc.get_or_add_tcPr()
            shd = OxmlElement("w:shd")
            shd.set(qn("w:val"), "clear")
            shd.set(qn("w:color"), "auto")
            shd.set(qn("w:fill"), "1F497D")
            tcPr.append(shd)

    def _format_cost(self, obj: dict) -> str:
        amount = obj.get("cost_amount", "")
        currency = obj.get("cost_currency", "PLN")
        pln = obj.get("cost_pln", "")
        if not amount:
            return ""
        if currency == "PLN":
            return f"{amount} PLN"
        return f"{amount} {currency} (~{pln} PLN)"
