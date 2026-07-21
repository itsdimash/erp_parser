"""Step 1 - Analyze every page.

For each page we determine: table presence, selectable text, OCR need,
row/column counts, product-keyword hits, graphics dominance, and an overall
procurement-data confidence score.

pdfplumber handles vector text + table geometry. PyMuPDF (fitz) gives us raster
image coverage and vector-drawing counts, which is how we tell a drawing/plan
page apart from a data page.
"""

from __future__ import annotations

import pdfplumber
import fitz  # PyMuPDF

from .config import ParserConfig
from .models import PageAnalysis
from .text_utils import normalize_ws, count_keyword_hits
from .ocr import ocr_image_to_text


# pdfplumber table settings: try lines first, fall back to text alignment.
_TABLE_SETTINGS_LINES = {
    "vertical_strategy": "lines",
    "horizontal_strategy": "lines",
}
_TABLE_SETTINGS_TEXT = {
    "vertical_strategy": "text",
    "horizontal_strategy": "text",
    "min_words_vertical": 2,
    "min_words_horizontal": 2,
}


class PageAnalyzer:
    def __init__(self, config: ParserConfig, tessdata_dir: str | None = None):
        self.config = config
        self.tessdata_dir = tessdata_dir

    def analyze(self, pdf_path: str) -> list[PageAnalysis]:
        analyses: list[PageAnalysis] = []
        fitz_doc = fitz.open(pdf_path)
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    fpage = fitz_doc[i] if i < fitz_doc.page_count else None
                    analyses.append(self._analyze_page(i + 1, page, fpage))
        finally:
            fitz_doc.close()
        return analyses

    # ------------------------------------------------------------------ #
    def _analyze_page(self, page_number, page, fpage) -> PageAnalysis:
        cfg = self.config
        pa = PageAnalysis(page_number=page_number)

        # --- selectable text ---
        text = page.extract_text() or ""
        text = normalize_ws(text)
        pa.text_char_count = len(text)
        pa.has_selectable_text = pa.text_char_count >= cfg.min_chars_for_text
        pa.text_sample = text[:2000]

        # --- graphics analysis via PyMuPDF ---
        if fpage is not None:
            pa.image_area_ratio, pa.vector_drawing_count = self._graphics_metrics(fpage)
        pa.is_mostly_graphics = (
            pa.image_area_ratio >= cfg.graphics_dominant_ratio
            or (pa.vector_drawing_count > 150 and pa.text_char_count < 400)
        )

        # --- OCR decision ---
        pa.ocr_required = (
            cfg.ocr_enabled
            and pa.text_char_count < cfg.ocr_text_threshold
            and (pa.image_area_ratio > 0.05 or pa.vector_drawing_count == 0)
        )

        # If OCR is needed, pull text from the image so keyword detection works.
        ocr_text = ""
        if pa.ocr_required and fpage is not None:
            ocr_text = self._ocr_page_text(fpage)
            if ocr_text:
                pa.notes.append("text recovered via OCR")
                if len(ocr_text) > pa.text_char_count:
                    pa.text_sample = normalize_ws(ocr_text)[:2000]

        haystack = (text + " " + ocr_text)

        # --- tables ---
        tables = self._find_tables(page)
        if tables:
            pa.has_table = True
            # report the largest table's geometry
            largest = max(tables, key=lambda t: len(t) * (len(t[0]) if t else 0))
            pa.row_count = len(largest)
            pa.column_count = max((len(r) for r in largest), default=0)

        # --- keyword hits ---
        pa.keyword_hits = count_keyword_hits(haystack, cfg.product_keywords)

        # --- procurement confidence (0..1) ---
        pa.procurement_confidence = self._confidence(pa)
        return pa

    # ------------------------------------------------------------------ #
    @staticmethod
    def _graphics_metrics(fpage) -> tuple[float, int]:
        """Return (image_area_ratio, vector_drawing_count)."""
        page_rect = fpage.rect
        page_area = max(1.0, page_rect.width * page_rect.height)
        img_area = 0.0
        try:
            for img in fpage.get_image_info():
                bbox = img.get("bbox")
                if bbox:
                    w = max(0.0, bbox[2] - bbox[0])
                    h = max(0.0, bbox[3] - bbox[1])
                    img_area += w * h
        except Exception:
            pass
        try:
            drawings = fpage.get_drawings()
            vector_count = len(drawings)
        except Exception:
            vector_count = 0
        return min(1.0, img_area / page_area), vector_count

    def _ocr_page_text(self, fpage) -> str:
        try:
            mat = fitz.Matrix(self.config.ocr_dpi / 72, self.config.ocr_dpi / 72)
            pix = fpage.get_pixmap(matrix=mat)
            from PIL import Image
            import io

            img = Image.open(io.BytesIO(pix.tobytes("png")))
            return ocr_image_to_text(
                img, self.config.ocr_languages, self.tessdata_dir
            )
        except Exception:
            return ""

    def _find_tables(self, page) -> list[list[list[str]]]:
        tables: list[list[list[str]]] = []
        for settings in (_TABLE_SETTINGS_LINES, _TABLE_SETTINGS_TEXT):
            try:
                found = page.extract_tables(settings)
            except Exception:
                found = []
            for t in found or []:
                cleaned = [
                    [normalize_ws(c) if c else "" for c in row] for row in t
                ]
                # keep tables that meet minimum shape
                if (
                    len(cleaned) >= self.config.min_rows_for_table
                    and max((len(r) for r in cleaned), default=0)
                    >= self.config.min_columns_for_table
                ):
                    tables.append(cleaned)
            if tables:
                break  # prefer line-based detection if it found anything
        return tables

    @staticmethod
    def _confidence(pa: PageAnalysis) -> float:
        score = 0.0
        if pa.has_table:
            score += 0.45
        # keyword density
        kw = len(pa.keyword_hits)
        score += min(0.35, kw * 0.07)
        # multi-column tables are a strong procurement signal
        if pa.column_count >= 3:
            score += 0.15
        if pa.row_count >= 3:
            score += 0.05
        # graphics-dominated pages are unlikely to be data tables
        if pa.is_mostly_graphics:
            score -= 0.35
        if not pa.has_selectable_text and not pa.ocr_required:
            score -= 0.1
        return max(0.0, min(1.0, score))
