"""Step 3 - Detect product tables."""

from __future__ import annotations
import io
import pdfplumber
import fitz

from .config import ParserConfig
from .models import DetectedTable
from .text_utils import normalize_ws, map_headers
from .ocr import ocr_image_to_table

_TABLE_SETTINGS_LINES = {"vertical_strategy": "lines", "horizontal_strategy": "lines"}
_TABLE_SETTINGS_TEXT = {
    "vertical_strategy": "text",
    "horizontal_strategy": "text",
    "min_words_vertical": 2,
    "min_words_horizontal": 2,
}


class TableDetector:
    def __init__(self, config: ParserConfig, tessdata_dir: str | None = None):
        self.config = config
        self.tessdata_dir = tessdata_dir

    def detect(self, pdf_path: str, page_numbers: list[int]) -> list[DetectedTable]:
        if not page_numbers:
            return []

        results: list[DetectedTable] = []
        wanted = set(page_numbers)
        fitz_doc = fitz.open(pdf_path)

        anchor_found = False

        def process_table(dt: DetectedTable | None):
            nonlocal anchor_found
            if not dt:
                return

            has_identity = "name" in dt.column_map or "description" in dt.column_map
            has_quantity = "quantity" in dt.column_map

            # THE FIX: Real equipment tables have units (шт) or codes.
            # Room indexes (floor plans) do not.
            has_unit = "unit" in dt.column_map
            has_code = "code" in dt.column_map

            # Demand a unit or code to definitively prove this is the start of the spec table!
            if not anchor_found and (
                has_identity and has_quantity and (has_unit or has_code)
            ):
                anchor_found = True

            if anchor_found:
                results.append(dt)

        try:
            with pdfplumber.open(pdf_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    pnum = i + 1
                    if pnum not in wanted:
                        continue

                    raw_tables = self._extract_vector_tables(page)

                    if not raw_tables:
                        fpage = fitz_doc[i] if i < fitz_doc.page_count else None
                        ocr_rows = self._ocr_table(fpage)
                        if ocr_rows:
                            dt = self._build_table(pnum, ocr_rows, source="ocr")
                            process_table(dt)
                        continue

                    for raw in raw_tables:
                        dt = self._build_table(pnum, raw, source="vector")
                        process_table(dt)
        finally:
            fitz_doc.close()

        return results

    def _extract_vector_tables(self, page) -> list[list[list[str]]]:
        tables: list[list[list[str]]] = []
        for settings in (_TABLE_SETTINGS_LINES, _TABLE_SETTINGS_TEXT):
            try:
                found = page.extract_tables(settings)
            except Exception:
                found = []
            for t in found or []:
                cleaned = [[normalize_ws(c) if c else "" for c in row] for row in t]
                cleaned = [r for r in cleaned if any(c for c in r)]
                if len(cleaned) >= 2 and max((len(r) for r in cleaned), default=0) >= 2:
                    tables.append(cleaned)
            if tables:
                break
        return tables

    def _ocr_table(self, fpage) -> list[list[str]]:
        if fpage is None:
            return []
        try:
            mat = fitz.Matrix(self.config.ocr_dpi / 72, self.config.ocr_dpi / 72)
            pix = fpage.get_pixmap(matrix=mat)
            from PIL import Image

            img = Image.open(io.BytesIO(pix.tobytes("png")))
            rows = ocr_image_to_table(img, self.config.ocr_languages, self.tessdata_dir)
            rows = [r for r in rows if len(r) >= 2]
            return rows if len(rows) >= 2 else []
        except Exception:
            return []

    def _build_table(self, page_number, raw, source) -> DetectedTable | None:
        width = max(len(r) for r in raw)
        grid = [r + [""] * (width - len(r)) for r in raw]

        best_header_idx = 0
        best_map: dict[str, int] = {}

        # 1. THE GOST BYPASS: Look for the [1, 2, ..., 7, 8, 9] row first!
        for hidx in range(min(10, len(grid))):
            row = grid[hidx]
            digits = [c.strip() for c in row if c.strip().isdigit()]
            if "1" in digits and "2" in digits and "7" in digits:
                cmap = {}
                for c_idx, val in enumerate(row):
                    v = val.strip()
                    if v == "1":
                        cmap["item_no"] = c_idx
                    elif v == "2":
                        cmap["name"] = c_idx
                    elif v == "4":
                        cmap["code"] = c_idx
                    elif v == "6":
                        cmap["unit"] = c_idx
                    elif v == "7":
                        cmap["quantity"] = c_idx
                if "name" in cmap and "quantity" in cmap:
                    best_map = cmap
                    best_header_idx = hidx
                    break

        # 2. STANDARD TEXT MATCHING
        if not best_map:
            best_field_count = -1
            for hidx in range(min(8, len(grid))):
                cmap = map_headers(grid[hidx], self.config)

                if "quantity" not in cmap:
                    for c_idx, cell_val in enumerate(grid[hidx]):
                        cln = cell_val.lower().replace(".", "").strip()
                        if cln in ("кол", "кол-во", "количество"):
                            cmap["quantity"] = c_idx
                            break

                field_count = len(cmap)
                if field_count > best_field_count:
                    best_field_count = field_count
                    best_map = cmap
                    best_header_idx = hidx

        # 3. DATA INFERENCE
        if not best_map:
            inferred = self._infer_structure_from_data(grid)
            if inferred:
                best_map = inferred
                best_header_idx = 0
            else:
                return None

        has_identity = ("name" in best_map) or ("description" in best_map)
        if not has_identity or len(best_map) < 2:
            return None

        header = grid[best_header_idx]
        data_rows = [r for r in grid[best_header_idx + 1 :] if any(c for c in r)]

        id_col = best_map.get("name", best_map.get("description"))
        if not self._identity_column_is_valid(id_col, data_rows):
            return None

        if not self._has_real_quantity_or_price(best_map, data_rows):
            return None

        dt = DetectedTable(
            page_number=page_number,
            header=header,
            rows=data_rows,
            column_map=best_map,
            source=source,
        )
        dt.table_confidence = self._table_confidence(dt)
        return dt

    def _infer_structure_from_data(
        self, grid: list[list[str]]
    ) -> dict[str, int] | None:
        if len(grid) < 2:
            return None

        data_rows = [r for r in grid[1:] if any(c.strip() for c in r)]
        if not data_rows:
            return None

        width = max(len(r) for r in grid)
        units = {
            "шт",
            "шт.",
            "штук",
            "компл",
            "комплект",
            "компл.",
            "к-т",
            "м",
            "м.",
            "м2",
            "м²",
            "м3",
            "м³",
            "пог.м",
            "п.м",
            "м.п",
            "кг",
            "г",
            "т",
            "л",
            "уп",
            "упак",
            "пара",
            "набор",
            "рулон",
            "pcs",
            "pc",
            "set",
            "kit",
            "unit",
            "ea",
        }

        def col_values(ci):
            vals = []
            for r in data_rows:
                v = r[ci].strip() if ci < len(r) else ""
                if v:
                    vals.append(v)
            return vals

        def frac_int(vals):
            if not vals:
                return 0.0
            return sum(1 for v in vals if v.isdigit()) / len(vals)

        def frac_unit(vals):
            if not vals:
                return 0.0
            return sum(
                1 for v in vals if v.lower().rstrip(".") in units or v.lower() in units
            ) / len(vals)

        def frac_code(vals):
            if not vals:
                return 0.0
            n = 0
            for v in vals:
                digits = sum(ch.isdigit() for ch in v)
                if ("-" in v or "/" in v) and digits >= 3:
                    n += 1
            return n / len(vals)

        def frac_cyr_text(vals):
            if not vals:
                return 0.0
            n = sum(
                1
                for v in vals
                if len(v) >= 8 and any("\u0400" <= ch <= "\u04ff" for ch in v)
            )
            return n / len(vals)

        name_c = code_c = unit_c = qty_c = itemno_c = None
        name_score = code_score = unit_score = qty_score = -1.0

        populated = []
        for ci in range(width):
            vals = col_values(ci)
            if len(vals) < max(2, len(data_rows) * 0.2):
                continue
            populated.append(ci)
            avg_len = sum(len(v) for v in vals) / len(vals)

            ft = frac_cyr_text(vals)
            if ft > 0.3 and avg_len > name_score:
                name_score, name_c = avg_len, ci

            fc = frac_code(vals)
            if fc > 0.3 and fc > code_score:
                code_score, code_c = fc, ci

            fu = frac_unit(vals)
            if fu > 0.3 and fu > unit_score:
                unit_score, unit_c = fu, ci

        def is_position_column(vals):
            nums = []
            for v in vals:
                if not v.isdigit():
                    return False
                nums.append(int(v))
            if len(nums) < 1:
                return False
            return nums[0] <= 2 and all(b > a for a, b in zip(nums, nums[1:]))

        for ci in populated:
            if ci in (name_c, code_c, unit_c):
                continue
            if is_position_column(col_values(ci)):
                itemno_c = ci
                break

        for ci in populated:
            if ci in (name_c, code_c, unit_c, itemno_c):
                continue
            vals = col_values(ci)
            fi = frac_int(vals)
            if fi > 0.6:
                score = fi + (0.5 if unit_c is not None and ci > unit_c else 0)
                if score > qty_score:
                    qty_score, qty_c = score, ci

        inferred = {}
        if name_c is not None:
            inferred["name"] = name_c
        if code_c is not None and code_c != name_c:
            inferred["code"] = code_c
        if unit_c is not None and unit_c not in (name_c, code_c):
            inferred["unit"] = unit_c
        if qty_c is not None and qty_c not in (name_c, code_c, unit_c):
            inferred["quantity"] = qty_c
        if itemno_c is not None and itemno_c not in (name_c, code_c, unit_c, qty_c):
            inferred["item_no"] = itemno_c

        has_identity = "name" in inferred or "description" in inferred
        if has_identity and len(inferred) >= 2:
            return inferred
        return None

    def _has_real_quantity_or_price(self, col_map, data_rows) -> bool:
        if "price" in col_map:
            return True
        units = {
            "шт",
            "шт.",
            "штук",
            "компл",
            "комплект",
            "компл.",
            "к-т",
            "м",
            "м.",
            "м2",
            "м²",
            "м3",
            "м³",
            "пог.м",
            "п.м",
            "м.п",
            "кг",
            "г",
            "т",
            "л",
            "уп",
            "упак",
            "пара",
            "набор",
            "рулон",
            "pcs",
            "pc",
            "set",
            "kit",
            "unit",
            "ea",
        }

        def col_nonempty(ci):
            out = []
            for r in data_rows:
                v = r[ci].strip() if ci is not None and ci < len(r) else ""
                if v:
                    out.append(v)
            return out

        qcol = col_map.get("quantity")
        if qcol is not None:
            vals = col_nonempty(qcol)
            if vals:

                def is_clean_count(v: str) -> bool:
                    if "/" in v or ":" in v or "-" in v:
                        return False
                    try:
                        float(v.replace(",", ".").replace("*", "").strip())
                        return True
                    except ValueError:
                        return False

                if sum(1 for v in vals if is_clean_count(v)) / len(vals) >= 0.6:
                    return True

        ucol = col_map.get("unit")
        if ucol is not None and "code" in col_map:
            uvals = col_nonempty(ucol)
            if uvals:
                if (
                    sum(
                        1
                        for v in uvals
                        if v.lower().rstrip(".") in units or v.lower() in units
                    )
                    / len(uvals)
                    >= 0.5
                ):
                    return True
        return False

    def _identity_column_is_valid(self, id_col, data_rows) -> bool:
        if id_col is None or not data_rows:
            return False
        values = [
            (r[id_col] or "").strip()
            for r in data_rows
            if id_col < len(r) and (r[id_col] or "").strip()
        ]
        if not values:
            return False
        is_large_table = len(data_rows) >= 40
        return (
            len(values) / len(data_rows) >= (0.30 if is_large_table else 0.40)
        ) and (
            sum(len(v) for v in values) / len(values)
            >= (3.0 if is_large_table else 5.0)
        )

    def _table_confidence(self, dt: DetectedTable) -> float:
        score = 0.0
        fields = set(dt.column_map)
        if "name" in fields or "description" in fields:
            score += 0.4
        if "quantity" in fields:
            score += 0.2
        if "unit" in fields:
            score += 0.1
        if "code" in fields:
            score += 0.1
        if "price" in fields:
            score += 0.1
        if len(dt.header) >= 3:
            score += 0.05
        if len(dt.rows) >= 2:
            score += 0.05
        if dt.source == "ocr":
            score *= 0.8
        return max(0.0, min(1.0, score))
