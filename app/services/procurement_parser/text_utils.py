"""Shared text helpers: normalization, number parsing, and the semantic
header -> canonical-field matcher used in Step 3.
"""

from __future__ import annotations

import re
from typing import Optional

from rapidfuzz import fuzz

from .config import ParserConfig


_WS_RE = re.compile(r"\s+")
_NUM_RE = re.compile(r"[-+]?\d[\d\s.,']*\d|\d")
_CID_RE = re.compile(r"\(cid:\d+\)")  # Catch font artifacts


def normalize_ws(text: str) -> str:
    """Collapse whitespace/newlines into single spaces and remove artifacts."""
    if text is None:
        return ""
    t = str(text)
    t = _CID_RE.sub("", t)  # Strip (cid:556) glitches
    return _WS_RE.sub(" ", t).strip()


def normalize_header(text: str) -> str:
    """Lowercase + strip punctuation noise for header comparison."""
    t = normalize_ws(text).lower()
    t = t.replace("ё", "е")
    t = re.sub(r"[._:;()\[\]{}/\\\"']+", " ", t)
    return normalize_ws(t)


def normalize_name(text: str) -> str:
    """Normalize a product name for matching (Step 4 normalize)."""
    t = normalize_ws(text)
    # unify common separators and quote styles
    t = t.replace("\u00a0", " ").replace("«", '"').replace("»", '"')
    t = re.sub(r"\s*[-–—]\s*", "-", t)  # standardize dashes
    t = re.sub(r"\s{2,}", " ", t)
    return t.strip()


def parse_quantity(text: str) -> Optional[float]:
    """Extract a numeric quantity from a possibly-noisy cell."""
    if text is None:
        return None
    m = _NUM_RE.search(str(text))
    if not m:
        return None
    raw = m.group(0)
    # Remove thousands separators (spaces / apostrophes), unify decimal comma.
    raw = raw.replace(" ", "").replace("'", "")
    if "," in raw and "." in raw:
        # assume "." thousands, "," decimal if comma is last
        if raw.rfind(",") > raw.rfind("."):
            raw = raw.replace(".", "").replace(",", ".")
        else:
            raw = raw.replace(",", "")
    elif "," in raw:
        raw = raw.replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def best_canonical_field(
    header_cell: str, config: ParserConfig
) -> tuple[Optional[str], float]:
    """Map a single header cell to the best-matching canonical field.

    Returns (field_name, score 0..100). Matching is token-aware so short
    synonyms ("ед", "no", "код") cannot match as substrings inside unrelated
    words (e.g. "сл**ед**ует"). Does NOT depend on exact spelling, but does
    avoid the false positives that plain substring/fuzzy matching produces on
    prose. Header cells are expected to be short labels; long cells (prose) are
    penalized.
    """
    norm = normalize_header(header_cell)
    if not norm:
        return None, 0.0

    tokens = set(norm.split())
    # Prose cells are not headers. A header label is short.
    word_count = len(norm.split())
    prose_penalty = word_count > 6 or len(norm) > 60

    best_field: Optional[str] = None
    best_score = 0.0

    for field_name, synonyms in config.header_synonyms.items():
        for syn in synonyms:
            syn_n = normalize_header(syn)
            if not syn_n:
                continue
            syn_len = len(syn_n)
            multiword = " " in syn_n

            score = 0.0
            if norm == syn_n:
                score = 100.0
            elif multiword and syn_n in norm:
                score = 96.0
            elif (not multiword) and syn_n in tokens:
                # whole-word token match
                score = 95.0
            elif syn_len >= 4 and (syn_n in norm):
                # substring only allowed for reasonably long synonyms
                score = 88.0
            elif syn_len >= 4 and not prose_penalty:
                # fuzzy only for longer synonyms, never on prose cells
                f = fuzz.token_sort_ratio(norm, syn_n)
                # require comparable lengths to avoid tiny-vs-huge matches
                if min(len(norm), syn_len) / max(len(norm), syn_len) >= 0.5:
                    score = f
            if prose_penalty:
                score *= 0.4
            if score > best_score:
                best_score = score
                best_field = field_name

    if best_score >= config.header_fuzzy_threshold:
        return best_field, best_score
    return None, best_score


def map_headers(header: list[str], config: ParserConfig) -> dict[str, int]:
    """Map a header row to {canonical_field: column_index}.

    Resolves conflicts by keeping the highest-scoring column per field. A column
    that strongly looks like 'name' will not be stolen by a weak 'description'.
    """
    # candidate[(field)] = (score, col_index)
    best_per_field: dict[str, tuple[float, int]] = {}
    used_cols: dict[int, tuple[str, float]] = {}

    scored: list[tuple[float, int, str]] = []
    for idx, cell in enumerate(header):
        field_name, score = best_canonical_field(cell, config)
        if field_name:
            scored.append((score, idx, field_name))

    # Greedy assignment, highest score first.
    for score, idx, field_name in sorted(scored, key=lambda x: -x[0]):
        if idx in used_cols:
            continue
        prev = best_per_field.get(field_name)
        if prev is None or score > prev[0]:
            best_per_field[field_name] = (score, idx)
            used_cols[idx] = (field_name, score)

    return {f: ci for f, (sc, ci) in best_per_field.items()}


def count_keyword_hits(text: str, keywords) -> list[str]:
    """Return the list of product keywords found in `text`."""
    low = " " + normalize_header(text) + " "
    hits = []
    for kw in keywords:
        kw_n = normalize_header(kw)
        if kw_n and kw_n in low:
            hits.append(kw)
    return hits
