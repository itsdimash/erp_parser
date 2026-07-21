"""Configuration: keywords, header synonyms, and tunable thresholds.

Everything here is data, not logic, so a client can override any of it without
touching the pipeline code. Matching is *semantic-ish*: we combine token
synonyms with fuzzy comparison, so the parser does not depend on exact header
spelling (Step 3 requirement).
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Step 1: product-related keywords (EN + RU). Used for keyword_hits / confidence
# ---------------------------------------------------------------------------
PRODUCT_KEYWORDS: tuple[str, ...] = (
    # EN
    "quantity", "qty", "unit", "item", "part number", "part no", "model",
    "article", "sku", "product", "equipment", "specification", "bill of materials",
    "bom", "price", "cost", "supplier", "manufacturer", "description",
    # RU
    "наименование", "описание", "количество", "кол-во", "ед", "единица",
    "артикул", "модель", "код", "цена", "стоимость", "позиция", "поз",
    "оборудование", "спецификация", "ведомость", "товар", "изделие",
    "производитель", "поставщик",
)


# ---------------------------------------------------------------------------
# Step 3: header synonyms -> canonical field.
# Lowercased substrings; the matcher also applies fuzzy comparison so small
# misspellings / OCR errors still resolve.
# ---------------------------------------------------------------------------
HEADER_SYNONYMS: dict[str, tuple[str, ...]] = {
    "item_no": (
        "№", "no", "n°", "#", "поз", "позиция", "item no", "item", "п/п",
        "пп", "line", "sr", "sl", "s.no",
    ),
    "code": (
        "артикул", "код", "code", "part number", "part no", "part #", "p/n",
        "model", "модель", "sku", "art", "cat", "кат", "каталожный",
        "reference", "ref", "obj",
    ),
    "name": (
        "наименование", "название", "товар", "изделие", "продукт", "product",
        "name", "item name", "оборудование", "equipment", "позиция наименование",
        "наименование товара", "номенклатура",
    ),
    "description": (
        "описание", "description", "характеристика", "характеристики", "spec",
        "specs", "specification", "технические характеристики", "примечание",
        "детали", "details", "remarks",
    ),
    "quantity": (
        "количество", "кол-во", "колво", "кол", "quantity", "qty", "qnty",
        "amount", "q'ty", "число",
    ),
    "unit": (
        "ед", "ед.", "ед. изм", "ед.изм", "единица", "единица измерения", "еи",
        "unit", "uom", "u/m", "measure", "меры",
    ),
    "price": (
        "цена", "стоимость", "price", "cost", "unit price", "rate", "сумма",
        "amount", "цена за единицу",
    ),
}


# ---------------------------------------------------------------------------
# Step 2: classification keywords per non-product category.
# ---------------------------------------------------------------------------
CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "TABLE_OF_CONTENTS": (
        "содержание", "оглавление", "table of contents", "contents", "index",
    ),
    "TECHNICAL_DESCRIPTION": (
        "техническое описание", "пояснительная записка", "technical description",
        "general description", "introduction", "общие сведения", "назначение",
    ),
    "REGULATIONS": (
        "гост", "снип", "сп ", "сanpin", "санпин", "норматив", "стандарт",
        "regulation", "standard", "norm", "compliance", "требования",
        "нормативн", "iso ", "din ", "en ",
    ),
    "FLOOR_PLANS": (
        "план этажа", "поэтажный план", "floor plan", "этаж", "план помещ",
        "layout", "экспликация",
    ),
    "DRAWINGS": (
        "чертеж", "чертёж", "схема", "drawing", "diagram", "разрез", "фасад",
        "elevation", "section view", "детализация",
    ),
    # product sub-categories (used to disambiguate the 4 processable types)
    "BILL_OF_MATERIALS": (
        "ведомость", "спецификация материалов", "bill of materials", "bom",
        "ведомость материалов", "ведомость объемов",
    ),
    "EQUIPMENT_SPECIFICATION": (
        "спецификация оборудования", "equipment specification", "equipment list",
        "перечень оборудования", "опросный лист", "ведомость оборудования",
    ),
}


@dataclass
class ParserConfig:
    """Tunable thresholds for the analysis + extraction stages."""

    # --- Step 1 ---
    min_chars_for_text: int = 40          # below this a page is "no selectable text"
    ocr_text_threshold: int = 80          # text below this + graphics => OCR
    graphics_dominant_ratio: float = 0.35  # image area fraction => "mostly graphics"
    ocr_dpi: int = 300
    ocr_languages: str = "rus+eng"
    ocr_enabled: bool = True

    # --- Step 3 ---
    header_fuzzy_threshold: float = 72.0   # lowered to catch non-standard headers on large tables
    min_columns_for_table: int = 2
    min_rows_for_table: int = 1

    # --- Step 5 (fuzzy matching against company data) ---
    match_threshold_high: float = 88.0     # >= => confident match
    match_threshold_low: float = 72.0      # >= => candidate match (still accepted)

    # product keywords / synonyms (overridable)
    product_keywords: tuple[str, ...] = field(default_factory=lambda: PRODUCT_KEYWORDS)
    header_synonyms: dict[str, tuple[str, ...]] = field(
        default_factory=lambda: {k: v for k, v in HEADER_SYNONYMS.items()}
    )
    category_keywords: dict[str, tuple[str, ...]] = field(
        default_factory=lambda: {k: v for k, v in CATEGORY_KEYWORDS.items()}
    )
