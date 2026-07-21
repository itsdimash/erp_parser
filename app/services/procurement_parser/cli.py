"""Command-line interface.

Example (PDF):
    python -m procurement_parser.cli input.pdf -o quotation.xlsx \\
        --template company_template.xlsx \\
        --tessdata ./tessdata --report

Example (Excel):
    python -m procurement_parser.cli input.xlsx -o quotation.xlsx \\
        --template company_template.xlsx

Example (Word):
    python -m procurement_parser.cli input.docx -o quotation.xlsx \\
        --template company_template.xlsx
"""

from __future__ import annotations

import argparse
import logging
import sys

from .config import ParserConfig
from .pipeline import Pipeline, PipelineConfig, SUPPORTED_EXTENSIONS


def main(argv=None):
    p = argparse.ArgumentParser(description="Intelligent procurement parser (PDF or Excel input)")
    p.add_argument("input_file", help=f"input file path {SUPPORTED_EXTENSIONS}")
    p.add_argument("-o", "--output", default="quotation.xlsx")
    p.add_argument("--template", help="company quotation template (.xlsx)")
    p.add_argument("--tessdata", help="directory with *.traineddata for OCR (PDF only)")
    p.add_argument("--no-ocr", action="store_true", help="disable OCR (PDF only)")
    p.add_argument("--report", action="store_true", help="print per-page report (PDF only)")

    p.add_argument("-v", "--verbose", action="store_true")

    args = p.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(message)s",
    )

    parser_cfg = ParserConfig(ocr_enabled=not args.no_ocr)
    cfg = PipelineConfig(
        parser=parser_cfg, tessdata_dir=args.tessdata, template_path=args.template
    )
    pipeline = Pipeline(cfg)

    result = pipeline.run(args.input_file, args.output)

    if args.report:
        print(pipeline.page_report(result))
        print()
    print(f"Products extracted: {len(result.products)}")
    print(f"Quotation written:  {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
