"""OCR utilities.

Two jobs:
  1. OCR a page image to plain text (for classification / keyword detection).
  2. Best-effort reconstruction of a *table* from a scanned page using
     pytesseract's word-level bounding boxes (image_to_data). This is how the
     pipeline handles PDFs whose tables are images rather than vector text.

OCR is optional: if tesseract or a language pack is missing, callers should
degrade gracefully (the pipeline catches exceptions and continues).
"""

from __future__ import annotations

import os
from typing import Optional

try:
    import pytesseract

    _OCR_IMPORTS_OK = True
except Exception:  # pragma: no cover
    _OCR_IMPORTS_OK = False


def _config_env(tessdata_dir: Optional[str]) -> str:
    if tessdata_dir:
        os.environ["TESSDATA_PREFIX"] = tessdata_dir
    return ""


def ocr_image_to_text(
    pil_image, languages: str = "rus+eng", tessdata_dir: Optional[str] = None
) -> str:
    if not _OCR_IMPORTS_OK:
        return ""
    _config_env(tessdata_dir)
    try:
        return pytesseract.image_to_text(pil_image, lang=languages)
    except Exception:
        # fall back to english only
        try:
            return pytesseract.image_to_text(pil_image, lang="eng")
        except Exception:
            return ""


def ocr_image_to_table(
    pil_image,
    languages: str = "rus+eng",
    tessdata_dir: Optional[str] = None,
    row_tol_ratio: float = 0.6,
    col_gap_ratio: float = 1.8,
) -> list[list[str]]:
    """Reconstruct an approximate table grid from a scanned image.

    Strategy:
      * Get word boxes via image_to_data.
      * Group words into rows by vertical position (line_num + y proximity).
      * Within each row, split into columns where the horizontal gap between
        consecutive words is unusually large.

    Returns a list of rows (each a list of cell strings). Empty if OCR fails.
    This is heuristic and intentionally conservative.
    """
    if not _OCR_IMPORTS_OK:
        return []
    _config_env(tessdata_dir)
    try:
        data = pytesseract.image_to_data(
            pil_image, lang=languages, output_type=pytesseract.Output.DICT
        )
    except Exception:
        try:
            data = pytesseract.image_to_data(
                pil_image, lang="eng", output_type=pytesseract.Output.DICT
            )
        except Exception:
            return []

    words = []
    n = len(data["text"])
    heights = []
    for i in range(n):
        txt = (data["text"][i] or "").strip()
        try:
            conf = float(data["conf"][i])
        except (ValueError, TypeError):
            conf = -1
        if not txt or conf < 30:
            continue
        words.append(
            {
                "text": txt,
                "left": data["left"][i],
                "top": data["top"][i],
                "width": data["width"][i],
                "height": data["height"][i],
                "block": data["block_num"][i],
                "par": data["par_num"][i],
                "line": data["line_num"][i],
            }
        )
        heights.append(data["height"][i])

    if not words:
        return []

    median_h = sorted(heights)[len(heights) // 2]
    max(4, median_h * row_tol_ratio)

    # Group by (block, par, line) which tesseract already computes per text line.
    lines: dict[tuple, list[dict]] = {}
    for w in words:
        key = (w["block"], w["par"], w["line"])
        lines.setdefault(key, []).append(w)

    # Order lines by their average vertical position.
    ordered = sorted(lines.values(), key=lambda ws: sum(x["top"] for x in ws) / len(ws))

    rows: list[list[str]] = []
    for line_words in ordered:
        line_words.sort(key=lambda w: w["left"])
        # Column splitting by large horizontal gaps.
        cells: list[str] = []
        current = [line_words[0]["text"]]
        prev_right = line_words[0]["left"] + line_words[0]["width"]
        avg_char = max(median_h * 0.6, 6)
        for w in line_words[1:]:
            gap = w["left"] - prev_right
            if gap > avg_char * col_gap_ratio:
                cells.append(" ".join(current))
                current = [w["text"]]
            else:
                current.append(w["text"])
            prev_right = w["left"] + w["width"]
        cells.append(" ".join(current))
        rows.append(cells)

    return rows
