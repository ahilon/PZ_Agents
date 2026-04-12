"""File Processor Agent — konwersja plików wejściowych (PDF/PNG/JPG) do base64 dla VisionAgent."""
import base64
import logging
from pathlib import Path
from typing import Any

from agents.base_agent import BaseAgent
from src.models.agent import Task

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Jesteś agentem przetwarzania plików wejściowych.
Konwertujesz pliki PDF, PNG i JPG do formatu gotowego do analizy przez VisionAgent.
Nie analizujesz treści — tylko przygotowujesz dane techniczne.
"""

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".pdf"}

MIME_MAP = {
    ".png":  "image/png",
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".pdf":  "image/jpeg",  # PDF konwertujemy do jpeg
}


class FileProcessorAgent(BaseAgent):
    """
    Przetwarza plik wejściowy (PDF/PNG/JPG) i zwraca listę stron jako base64.

    Parametry task:
      file_path  (str)  — ścieżka do pliku
      dpi        (int)  — rozdzielczość dla PDF (domyślnie: 150)
      max_pages  (int)  — maksymalna liczba stron PDF (domyślnie: 5)

    Zwraca:
      {
        "file_path": "...",
        "file_type": "pdf" | "image",
        "pages": [
          {
            "page_number": 1,
            "image_base64": "...",
            "mime_type": "image/jpeg"
          }
        ],
        "page_count": 1,
        "status": "completed"
      }
    """

    async def _process_task(self, task: Task) -> Any:
        p = task.parameters
        file_path = Path(p.get("file_path", ""))

        if not file_path.exists():
            return {"status": "failed", "summary": f"Plik nie istnieje: {file_path}"}

        ext = file_path.suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            return {
                "status": "failed",
                "summary": f"Nieobsługiwany format: '{ext}'. Obsługiwane: {', '.join(SUPPORTED_EXTENSIONS)}",
            }

        if ext == ".pdf":
            return self._process_pdf(file_path, p.get("dpi", 150), p.get("max_pages", 5))
        return self._process_image(file_path)

    def _process_image(self, file_path: Path) -> dict:
        logger.info(f"FileProcessor: konwertuję obraz {file_path.name}")
        ext = file_path.suffix.lower()
        image_b64 = base64.b64encode(file_path.read_bytes()).decode("utf-8")
        mime = MIME_MAP.get(ext, "image/jpeg")
        return {
            "file_path": str(file_path),
            "file_type": "image",
            "pages": [{"page_number": 1, "image_base64": image_b64, "mime_type": mime}],
            "page_count": 1,
            "status": "completed",
            "summary": f"Obraz '{file_path.name}' gotowy do analizy.",
        }

    def _process_pdf(self, file_path: Path, dpi: int, max_pages: int) -> dict:
        try:
            import fitz  # PyMuPDF
        except ImportError:
            return {"status": "failed", "summary": "Brak biblioteki PyMuPDF. Uruchom: poetry add pymupdf"}

        logger.info(f"FileProcessor: konwertuję PDF {file_path.name} (dpi={dpi}, max={max_pages} stron)")

        try:
            doc = fitz.open(str(file_path))
        except Exception as e:
            return {"status": "failed", "summary": f"Błąd otwarcia PDF: {e}"}

        pages = []
        total = min(len(doc), max_pages)

        for page_num in range(total):
            page = doc[page_num]
            mat = fitz.Matrix(dpi / 72, dpi / 72)
            pix = page.get_pixmap(matrix=mat)
            img_bytes = pix.tobytes("jpeg")
            image_b64 = base64.b64encode(img_bytes).decode("utf-8")
            pages.append({
                "page_number": page_num + 1,
                "image_base64": image_b64,
                "mime_type": "image/jpeg",
            })

        doc.close()

        return {
            "file_path": str(file_path),
            "file_type": "pdf",
            "pages": pages,
            "page_count": len(pages),
            "status": "completed",
            "summary": f"PDF '{file_path.name}': {len(pages)} stron gotowych do analizy.",
        }
