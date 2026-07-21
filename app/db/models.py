"""
Модели БД для парсера:
  warehouse — что сейчас есть на складе  -> статус ON_STOCK
  history   — что раньше закупали/было    -> статус PREVIOUSLY_PURCHASED

Названия колонок — моё предположение под поля CompanyRecord.
Когда друзья пришлют реальную структуру БД — просто поправь имена колонок здесь.
"""

from __future__ import annotations

from sqlalchemy import String, Float, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Warehouse(Base):
    """Текущие остатки на складе."""

    __tablename__ = "warehouse"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)  # наименование
    code: Mapped[str] = mapped_column(String, default="")  # артикул
    unit: Mapped[str] = mapped_column(String, default="")  # ед. изм.
    quantity: Mapped[float | None] = mapped_column(Float, nullable=True)  # остаток
    cost_price: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )  # себестоимость
    supplier: Mapped[str] = mapped_column(String, default="")  # поставщик


class History(Base):
    """История закупок — было на складе, сейчас нет."""

    __tablename__ = "history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    code: Mapped[str] = mapped_column(String, default="")
    unit: Mapped[str] = mapped_column(String, default="")
    cost_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    supplier: Mapped[str] = mapped_column(String, default="")
