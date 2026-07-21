"""Step 2 - Classify each page.

Assigns exactly one PageCategory. The four "processable" categories
(Equipment Specification, BOM, Product Table, Price Table) are only assigned
when a recognizable product table was detected on the page; everything else is
routed to a descriptive category and later ignored.

Detection (Step 3) is run *before* classification on candidate pages so the
classifier can distinguish a real product table from prose or a drawing — but
extraction only ever proceeds for pages that land in a processable category,
which satisfies the "ignore all other pages" requirement.
"""

from __future__ import annotations

from typing import Optional

from .config import ParserConfig
from .models import PageAnalysis, DetectedTable, PageCategory
from .text_utils import normalize_header


class PageClassifier:
    def __init__(self, config: ParserConfig):
        self.config = config

    def classify(
        self,
        analysis: PageAnalysis,
        product_table: Optional[DetectedTable],
        total_pages: int,
    ) -> PageCategory:
        text = normalize_header(analysis.text_sample)
        ck = self.config.category_keywords

        # 1) Pages with a genuine product table -> one of the 4 processable types
        if product_table is not None and product_table.is_product_table \
                and product_table.table_confidence >= 0.45:
            return self._classify_product_table(product_table, text, ck)

        # 2) Non-table pages -> descriptive categories.
        # Table of contents
        if self._has_any(text, ck["TABLE_OF_CONTENTS"]) or self._looks_like_toc(
            analysis.text_sample
        ):
            return PageCategory.TABLE_OF_CONTENTS

        # Cover page: first page, sparse text, no table.
        if (
            analysis.page_number == 1
            and not analysis.has_table
            and analysis.text_char_count < 600
        ):
            return PageCategory.COVER_PAGE

        # Floor plans (drawings + plan keywords)
        if self._has_any(text, ck["FLOOR_PLANS"]) and (
            analysis.is_mostly_graphics or analysis.vector_drawing_count > 50
        ):
            return PageCategory.FLOOR_PLANS

        # Generic drawings: graphics-dominated or drawing keywords with little text
        if analysis.is_mostly_graphics or (
            self._has_any(text, ck["DRAWINGS"]) and analysis.text_char_count < 800
        ):
            return PageCategory.DRAWINGS

        # Regulations
        if self._has_any(text, ck["REGULATIONS"]):
            return PageCategory.REGULATIONS

        # Technical description: prose-heavy or matching keywords
        if self._has_any(text, ck["TECHNICAL_DESCRIPTION"]) or (
            analysis.has_selectable_text
            and not analysis.has_table
            and analysis.text_char_count > 600
        ):
            return PageCategory.TECHNICAL_DESCRIPTION

        return PageCategory.UNKNOWN

    # ------------------------------------------------------------------ #
    def _classify_product_table(self, table, text, ck) -> PageCategory:
        # Price table wins if a price column is present.
        if "price" in table.column_map:
            # but if it's clearly an equipment/BOM doc, still prefer those labels
            if self._has_any(text, ck["BILL_OF_MATERIALS"]):
                return PageCategory.BILL_OF_MATERIALS
            if self._has_any(text, ck["EQUIPMENT_SPECIFICATION"]):
                return PageCategory.EQUIPMENT_SPECIFICATION
            return PageCategory.PRICE_TABLE
        if self._has_any(text, ck["BILL_OF_MATERIALS"]):
            return PageCategory.BILL_OF_MATERIALS
        if self._has_any(text, ck["EQUIPMENT_SPECIFICATION"]):
            return PageCategory.EQUIPMENT_SPECIFICATION
        return PageCategory.PRODUCT_TABLE

    @staticmethod
    def _has_any(text: str, keywords) -> bool:
        for kw in keywords:
            if normalize_header(kw) in text:
                return True
        return False

    @staticmethod
    def _looks_like_toc(text: str) -> bool:
        # dotted leaders followed by page numbers: "Introduction......3"
        import re

        return bool(re.search(r"\.{4,}\s*\d+", text))
