"""Intelligent PDF procurement / equipment parser.

A layout-independent pipeline that analyzes any engineering PDF, finds the
pages that actually contain procurement data, extracts product tables,
matches them against *company* data, and produces a quotation spreadsheet.

The public entry point is `Pipeline` (see pipeline.py).
"""

from .models import (
    PageCategory,
    PageAnalysis,
    DetectedTable,
    Product,
    DocumentResult,
)
from .pipeline import Pipeline, PipelineConfig

__all__ = [
    "Pipeline",
    "PipelineConfig",
    "PageCategory",
    "PageAnalysis",
    "DetectedTable",
    "Product",
    "DocumentResult",
]

__version__ = "1.0.0"
