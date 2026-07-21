"""
Роут парсера.

Клиент присылает PDF или Excel (.xlsx) проекта  ->  парсер извлекает товары
(warehouse / history)                            ->  возвращаем готовый Excel на скачивание.

ВСЕ импорты движка парсера сделаны ленивыми (внутри функций). Причина:
__init__.py пакета парсера на верхнем уровне импортит pipeline (а тот —
pdfplumber и др.). Если импортировать что-либо из пакета на верху этого
файла, при сборке тестов в CI (где тяжёлых библиотек нет) всё падает.
Ленивые импорты позволяют приложению и базовым тестам подниматься без них.
"""

from __future__ import annotations

import os
import logging
import tempfile

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from fastapi.concurrency import run_in_threadpool
from starlette.background import BackgroundTask

logger = logging.getLogger("parser_router")

router = APIRouter(prefix="/parser", tags=["Parser"])

ALLOWED_EXTENSIONS = {".pdf", ".xlsx", ".docx"}
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _safe_remove(path: str) -> None:
    """Удалить файл, не падая если его уже нет."""
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


# Database / company-data logic removed: parser no longer depends on DB.


@router.post("/parse")
async def parse_document(
    file: UploadFile = File(...),
):
    """
    Принимает PDF, Excel (.xlsx) или Word (.docx), возвращает Excel (коммерческое предложение).
    """
    # 1. Проверяем расширение (до любых импортов парсера — быстрый отказ)
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Принимается только PDF, Excel (.xlsx) или Word (.docx). Получено: '{ext or 'без расширения'}'",
        )

    # 2. Читаем загруженный файл
    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Файл пустой")

    # 3. Ленивый импорт тяжёлого парсера — только когда реально нужен
    from app.services.procurement_parser.pipeline import Pipeline

    # 4. Сохраняем входной файл во временный файл, сохраняя реальное
    #    расширение — Pipeline.run() выбирает PDF-, Excel- или Word-путь
    #    именно по расширению файла на диске, а не по исходному имени.
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp_in:
        tmp_in.write(contents)
        input_path = tmp_in.name

    # 5. Готовим путь для выходного Excel
    out_fd, output_path = tempfile.mkstemp(suffix=".xlsx")
    os.close(out_fd)

    # 6. Запускаем парсер
    try:
        # Pipeline no longer requires company data or DB access.
        pipeline = Pipeline()

        # pipeline is blocking -> run in threadpool so server stays responsive
        await run_in_threadpool(pipeline.run, input_path, output_path)

    except Exception as e:
        _safe_remove(input_path)
        _safe_remove(output_path)
        logger.exception("Ошибка парсинга")
        raise HTTPException(status_code=422, detail=f"Ошибка парсинга: {e}")

    # 7. Входной файл больше не нужен
    _safe_remove(input_path)

    # 8. Отдаём Excel; временный файл удалится после отправки ответа
    base_name = os.path.splitext(file.filename or "result")[0]
    download_name = f"quotation_{base_name}.xlsx"

    return FileResponse(
        output_path,
        media_type=XLSX_MIME,
        filename=download_name,
        background=BackgroundTask(_safe_remove, output_path),
    )
