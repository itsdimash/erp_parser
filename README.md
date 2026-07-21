# ERP Procurement Parser

[![Backend CI](https://github.com/your-org/ERP_parser/actions/workflows/backend-ci.yml/badge.svg)](https://github.com/your-org/ERP_parser/actions/workflows/backend-ci.yml)
[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/release/python-3130/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg?style=flat&logo=FastAPI&logoColor=white)](https://fastapi.tiangolo.com/)
[![Code Style: Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A high-performance, modular Python-based service and parser designed for automated ingestion, analysis, extraction, and standardization of procurement documents, ERP data, and financial records.

The **ERP Procurement Parser** ingests multi-format documents (Word, Excel, PDFs via OCR, and digital tables), classifies document layouts, extracts product/item specifications, matches vendor companies, and exports clean, structured datasets via REST API endpoints or standardized Excel summaries.

---

## 🌟 Key Features

- **Multi-Format Extraction**: Ingests Microsoft Word (`.docx`), Excel (`.xlsx`, `.xls`), and image/PDF formats using optical character recognition (OCR).
- **Intelligent Page & Layout Analysis**:
  - **Page Classifier**: Automatically categorizes pages (e.g., Cover, Item List, Terms & Conditions, Signatures).
  - **Table Detector**: Detects tabular structures, grid boundaries, and dynamic table headers across non-standard layouts.
  - **Page Analyzer**: Analyzes contextual text hierarchy and document sections.
- **Entity & Product Extraction**:
  - Extract detailed product metadata (SKU, description, unit price, quantity, tax, total value).
  - **Company Matcher**: Fuzzy matching and normalization of supplier/vendor names against known databases.
- **Dual Operating Modes**:
  - **RESTful API**: Fast, asynchronous Web API endpoints for integration into enterprise ERP pipelines.
  - **CLI Tool**: Command-line interface for local batch processing and offline parsing tasks.
- **Database Integration**: SQLAlchemy ORM session management and persistent models for parsed jobs and extracted line items.
- **Automated CI/CD**: Pre-configured GitHub Actions workflow for automated linting, unit testing, and integration testing.

---

## 🏗 Repository Structure

```text
ERP_parser/
├── .github/
│   └── workflows/
│       └── backend-ci.yml        # GitHub Actions CI workflow for backend tests
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── routers/
│   │       │   ├── health.py     # System health check routes
│   │       │   └── parser.py     # Procurement document parsing routes
│   │       └── api.py            # Main API v1 router aggregation
│   ├── core/
│   │   └── config.py             # Application settings & environment variables
│   ├── db/
│   │   ├── base.py               # Base ORM declarative model metadata
│   │   ├── models.py             # Database entities (Jobs, Products, Vendors)
│   │   └── session.py            # Database connection & session management
│   ├── schemas/
│   │   └── health.py             # Pydantic validation schemas for health endpoint
│   ├── services/
│   │   └── procurement_parser/   # Core domain logic & extraction pipeline
│   │       ├── cli.py            # CLI entrypoint handler
│   │       ├── config.py         # Parser-specific configuration settings
│   │       ├── data_sources.py   # Ingestion data adapters & source abstractions
│   │       ├── excel_extractor.py# Excel file reader and raw table parser
│   │       ├── excel_generator.py# Export tool generating formatted Excel reports
│   │       ├── models.py         # Internal data transfer objects (DTOs)
│   │       ├── ocr.py            # OCR engine integration for image/PDF parsing
│   │       ├── page_analyzer.py  # Visual & spatial page layout analyzer
│   │       ├── page_classifier.py# ML/Heuristic page layout classifier
│   │       ├── pipeline.py       # Orchestration pipeline for full end-to-end extraction
│   │       ├── product_extractor.py # Line item & product attribute parser
│   │       ├── table_detector.py # Table region boundaries detector
│   │       ├── text_utils.py     # Text cleaning & string normalization utilities
│   │       └── word_extractor.py # DOCX document text and table reader
│   └── main.py                   # FastAPI application initialization & middleware
├── tests/
│   ├── test_health.py            # Unit tests for health endpoints
│   └── test_parser_api.py        # Integration tests for document parsing API
├── .env.example                  # Environment variables template file
├── .gitignore                    # Standard Git ignore rules
└── README.md                     # Project documentation
```

---

## ⚡ Quick Start

### Prerequisites

- **Python**: Version 3.13 or higher
- **System Dependencies** (for OCR and document processing):
  - `tesseract-ocr` (optional, required if parsing scanned images/PDFs)

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/your-org/ERP_parser.git
   cd ERP_parser
   ```

2. **Create and activate a virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **Configure Environment Variables**:
   Copy `.env.example` to `.env` and adjust the variables according to your environment:
   ```bash
   cp .env.example .env
   ```

---

## 🚀 Usage

### 1. Running the FastAPI Web Server

Start the API service using Uvicorn:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Once running, access the interactive API documentation:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

### 2. Using the Command Line Interface (CLI)

You can run the procurement parser directly from the terminal for batch processing local files:

```bash
# Parse a document and export results to an Excel spreadsheet
python -m app.services.procurement_parser --input /path/to/procurement_doc.pdf --output /path/to/result.xlsx
```

Or run via the CLI script:
```bash
python app/services/procurement_parser/cli.py --file sample_tender.docx
```

---

## 🧪 Testing

The repository uses `pytest` for unit and integration testing.

Run the test suite:
```bash
pytest
```

Run tests with coverage reporting:
```bash
pytest --cov=app tests/
```

---

## 🔧 CI/CD Pipeline

Continuous Integration is configured via GitHub Actions (`.github/workflows/backend-ci.yml`). On every push or pull request to the `main` branch, the pipeline automatically:
1. Sets up Python 3.13.
2. Installs dependencies.
3. Executes code linter and formatting checks.
4. Runs unit and integration tests via `pytest`.

---

## 📜 License

Distributed under the [MIT License](LICENSE).
