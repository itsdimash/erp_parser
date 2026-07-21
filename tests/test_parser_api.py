"""
API-тесты эндпоинта парсера.

Базовые тесты (валидация) не требуют тяжёлых библиотек парсера и проходят в CI.
Тест с реальным PDF требует зависимостей парсера + tesseract, поэтому по умолчанию
пропускается. Чтобы запустить локально:  RUN_PARSER_INTEGRATION=1 pytest tests/ -v
"""

import os
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

RUN_INTEGRATION = os.getenv("RUN_PARSER_INTEGRATION") == "1"


# ──────────────────────────────────────────
# Базовые тесты валидации (без зависимостей парсера)
# ──────────────────────────────────────────


def test_parse_no_file():
    """Запрос без файла → 422 (FastAPI сам валидирует)"""
    response = client.post("/api/v1/parser/parse")
    assert response.status_code == 422


def test_parse_wrong_extension():
    """Неподдерживаемое расширение (.txt) → 400"""
    response = client.post(
        "/api/v1/parser/parse",
        files={"file": ("notes.txt", b"some text", "text/plain")},
    )
    assert response.status_code == 400


def test_parse_empty_file():
    """Пустой файл с правильным расширением → 400"""
    response = client.post(
        "/api/v1/parser/parse",
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )
    assert response.status_code == 400


# ──────────────────────────────────────────
# Интеграционный тест (реальный PDF -> Excel)
# Требует зависимостей парсера + tesseract. По умолчанию пропускается.
# ──────────────────────────────────────────


@pytest.mark.skipif(
    not RUN_INTEGRATION,
    reason="set RUN_PARSER_INTEGRATION=1 to run (needs parser deps + tesseract)",
)
def test_parse_real_pdf_returns_excel():
    examples_dir = "app/api/v1/parser/examples"
    pdfs = [f for f in os.listdir(examples_dir) if f.lower().endswith(".pdf")]
    if not pdfs:
        pytest.skip("Нет PDF в examples/")

    path = os.path.join(examples_dir, pdfs[0])
    with open(path, "rb") as f:
        response = client.post(
            "/api/v1/parser/parse",
            files={"file": (pdfs[0], f, "application/pdf")},
        )

    assert response.status_code == 200
    # ответ — это xlsx-файл
    assert response.headers["content-type"] == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert len(response.content) > 0
