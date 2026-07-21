"""The Pipeline ties the steps together.

PDF path (six steps):
    Step 1  PageAnalyzer      -> analyze every page
    Step 3* TableDetector     -> detect tables on candidate pages
    Step 2  PageClassifier    -> classify pages (uses table info)
    (keep only processable categories)
    Step 4  ProductExtractor  -> extract products from processable tables
    Step 5  CompanyMatcher    -> match against company data
    Step 6  ExcelGenerator    -> write the quotation

(*Detection is computed before classification so the classifier can recognize a
real product table, but extraction only runs on processable pages.)

Excel path (input is already structured, so steps 1-3 are skipped):
    Step 4  ExcelProductExtractor -> extract products directly from cells
    Step 6  ExcelGenerator        -> write the quotation

`Pipeline.run()` dispatches on the input file's extension (.pdf / .xlsx).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

from .config import ParserConfig
from .models import DocumentResult, PageCategory
from .page_analyzer import PageAnalyzer
from .table_detector import TableDetector
from .page_classifier import PageClassifier
from .product_extractor import ProductExtractor
from .excel_extractor import ExcelProductExtractor, ExcelColumnMap
from .excel_generator import ExcelGenerator

if TYPE_CHECKING:
    # Only needed for type hints below — the real import stays lazy (see
    # _run_word) so a missing/broken python-docx can't break PDF/Excel.
    from .word_extractor import WordColumnMap

logger = logging.getLogger("procurement_parser")

SUPPORTED_EXTENSIONS = (".pdf", ".xlsx", ".docx")


@dataclass
class PipelineConfig:
    parser: ParserConfig = field(default_factory=ParserConfig)
    tessdata_dir: Optional[str] = None  # dir containing *.traineddata
    template_path: Optional[str] = None  # company quotation template (.xlsx)
    excel_column_map: Optional[ExcelColumnMap] = None  # override xlsx input layout
    excel_sheet_name: Optional[str] = None  # override xlsx input sheet
    word_column_map: Optional[WordColumnMap] = None  # override docx input layout
    word_table_index: Optional[int] = (
        None  # override docx input table (default: scan all)
    )


class Pipeline:
    def __init__(self, config: PipelineConfig | None = None):
        self.config = config or PipelineConfig()
        cfg = self.config.parser
        td = self.config.tessdata_dir
        self.analyzer = PageAnalyzer(cfg, td)
        self.detector = TableDetector(cfg, td)
        self.classifier = PageClassifier(cfg)
        self.extractor = ProductExtractor(cfg)
        self.excel_extractor = ExcelProductExtractor(
            column_map=self.config.excel_column_map,
            sheet_name=self.config.excel_sheet_name,
        )
        self.word_extractor = None  # built lazily in _run_word: python-docx
        # is an optional dependency, only needed for .docx input, and must
        # not break PDF/Excel parsing if it's missing or broken.
        self.excel = ExcelGenerator()

    def run(self, input_path: str, output_path: str) -> DocumentResult:
        ext = os.path.splitext(input_path)[1].lower()
        if ext == ".pdf":
            return self._run_pdf(input_path, output_path)
        if ext == ".xlsx":
            return self._run_excel(input_path, output_path)
        if ext == ".docx":
            return self._run_word(input_path, output_path)
        raise ValueError(
            f"Unsupported input file type '{ext}'. Expected one of {SUPPORTED_EXTENSIONS}."
        )

    # ------------------------------------------------------------------ #
    def _run_pdf(self, pdf_path: str, output_path: str) -> DocumentResult:
        result = DocumentResult(pdf_path=pdf_path)

        # --- Step 1: analyze all pages ---
        result.page_analyses = self.analyzer.analyze(pdf_path)
        logger.info("Analyzed %d pages", len(result.page_analyses))

        # --- Step 3 (pre-pass): detect tables on candidate pages ---
        candidate_pages = [
            pa.page_number
            for pa in result.page_analyses
            if pa.has_table or pa.ocr_required
        ]
        all_tables = self.detector.detect(pdf_path, candidate_pages)
        # best product table per page (for classification)
        table_by_page: dict[int, object] = {}
        for t in all_tables:
            cur = table_by_page.get(t.page_number)
            if cur is None or t.table_confidence > cur.table_confidence:
                table_by_page[t.page_number] = t

        # --- Step 2: classify every page ---
        total = len(result.page_analyses)
        for pa in result.page_analyses:
            cat = self.classifier.classify(pa, table_by_page.get(pa.page_number), total)
            result.page_categories[pa.page_number] = cat

        logger.info("Processable pages: %s", result.processable_pages or "none")

        # --- keep only tables on processable pages ---
        processable = set(result.processable_pages)
        result.detected_tables = [
            t for t in all_tables if t.page_number in processable and t.is_product_table
        ]

        # --- Step 4: extract products ---
        result.products = self.extractor.extract(result.detected_tables)
        logger.info("Extracted %d products", len(result.products))

        # --- Step 6: generate Excel from extracted products ---
        self.excel.generate(result.products, output_path)
        logger.info("Wrote quotation: %s", output_path)
        return result

    # ------------------------------------------------------------------ #
    def _run_excel(self, xlsx_path: str, output_path: str) -> DocumentResult:
        result = DocumentResult(pdf_path=xlsx_path)

        # --- Step 4: extract products directly from the structured sheet ---
        result.products = self.excel_extractor.extract(xlsx_path)
        logger.info("Extracted %d products from Excel", len(result.products))

        # --- Step 6: generate Excel from extracted products ---
        self.excel.generate(result.products, output_path)
        logger.info("Wrote quotation: %s", output_path)
        return result

    # ------------------------------------------------------------------ #
    def _run_word(self, docx_path: str, output_path: str) -> DocumentResult:
        result = DocumentResult(pdf_path=docx_path)

        if self.word_extractor is None:
            # Lazy import: python-docx is only required for the .docx path,
            # and must not be able to break PDF/Excel parsing if it's
            # missing or fails to import for any reason.
            from .word_extractor import WordProductExtractor

            self.word_extractor = WordProductExtractor(
                column_map=self.config.word_column_map,
                table_index=self.config.word_table_index,
            )

        # --- Step 4: extract products directly from the structured table(s) ---
        result.products = self.word_extractor.extract(docx_path)
        logger.info("Extracted %d products from Word", len(result.products))

        # --- Step 6: generate Excel from extracted products ---
        self.excel.generate(result.products, output_path)
        logger.info("Wrote quotation: %s", output_path)
        return result

    # convenience: human-readable page report (PDF path only)
    def page_report(self, result: DocumentResult) -> str:
        if not result.page_analyses:
            return "No per-page report available (Excel input has no pages)."
        lines = ["Page  Category                  Conf  Table  Rows×Cols  OCR  KW"]
        for pa in result.page_analyses:
            cat = result.page_categories.get(pa.page_number, PageCategory.UNKNOWN)
            mark = "*" if cat.is_processable else " "
            lines.append(
                f"{pa.page_number:>3}{mark} {cat.value:<24} "
                f"{pa.procurement_confidence:>4.2f}  "
                f"{'yes' if pa.has_table else ' no':>3}  "
                f"{pa.row_count:>3}×{pa.column_count:<3}   "
                f"{'yes' if pa.ocr_required else ' no'}  "
                f"{len(pa.keyword_hits):>2}"
            )
        return "\n".join(lines)
