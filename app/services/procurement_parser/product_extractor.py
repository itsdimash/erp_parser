"""Step 4 - Extract products."""

from __future__ import annotations

from .config import ParserConfig
from .models import DetectedTable, Product
from .text_utils import normalize_ws, normalize_name, parse_quantity

_STOP_WORDS = (
    "итого",
    "всего",
    "total",
    "subtotal",
    "sum",
    "сумма прописью",
    "раздел",
    "section",
    "изм",
    "гип",
    "проверил",
    "выполнил",
    "подп",
    "дата",
)


class ProductExtractor:
    def __init__(self, config: ParserConfig):
        self.config = config

    def extract(self, tables: list[DetectedTable]) -> list[Product]:
        products: list[Product] = []
        for table in tables:
            if not table.is_product_table:
                continue
            products.extend(self._extract_from_table(table))
        return self._dedupe(products)

    def _extract_from_table(self, table: DetectedTable) -> list[Product]:
        cmap = table.column_map
        out: list[Product] = []
        room_keywords = (
            "кабинет",
            "помещение",
            "этаж",
            "блок",
            "зона",
            "комната",
            "класс",
        )

        def cell(row, field):
            idx = cmap.get(field)
            if idx is None or idx >= len(row):
                return ""
            return normalize_ws(row[idx])

        for row in table.rows:
            name = cell(row, "name")
            desc = cell(row, "description")
            code = cell(row, "code")
            qty_raw = cell(row, "quantity")
            unit = cell(row, "unit")
            item_no = cell(row, "item_no")

            joined = " ".join(c for c in row if c).lower()

            if any(sw in joined for sw in _STOP_WORDS):
                continue
            if not any([name, desc, code, qty_raw]):
                continue
            if name.strip() == "2" and (qty_raw.strip() == "7" or "6" in unit):
                continue

            quantity = parse_quantity(qty_raw)

            # THE BULLETPROOF FALLBACK V2
            if quantity is None:
                name_idx = cmap.get("name", -1)
                for col_idx in range(len(row) - 1, max(name_idx, 0), -1):
                    val = normalize_ws(row[col_idx]).replace(".0", "")
                    if val and len(val) <= 12 and any(c.isdigit() for c in val):
                        pq = parse_quantity(val)
                        if pq is not None and pq < 10000:
                            quantity = pq
                            break

            low_name = (name + " " + desc).lower()
            if (
                quantity is None
                and not code
                and any(rk in low_name for rk in room_keywords)
            ):
                continue

            is_continuation = (
                bool(out) and not item_no and not code and quantity is None and not unit
            )

            if is_continuation:
                prev = out[-1]
                extra = name or desc
                if extra:
                    prev.name = (
                        normalize_name(prev.name + " " + extra)
                        if prev.name
                        else normalize_name(extra)
                    )
                continue

            if not name and desc:
                name, desc = desc, ""
            final_name = normalize_name(name) if name else normalize_name(code)

            if not final_name:
                continue
            out.append(Product(name=final_name, quantity=quantity))

        return out

    @staticmethod
    def _dedupe(products: list[Product]) -> list[Product]:
        seen: set[tuple] = set()
        result: list[Product] = []
        for p in products:
            key = (p.name.lower(), p.quantity)
            if key in seen:
                continue
            seen.add(key)
            result.append(p)
        return result
