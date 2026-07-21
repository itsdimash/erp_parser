"""Company data sources for Step 5.

The matcher only ever reads from these. There is deliberately no network code
anywhere in this package: the parser cannot search the internet or invent
prices. To connect real systems, subclass `CompanyDataSource` (or use the CSV/
JSON/in-memory helpers) and hand them to `CompanyData`.
"""

from __future__ import annotations

import csv
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


# Roles correspond to the four sources named in the spec.
ROLE_PRODUCT_DB = "Product Database"
ROLE_WAREHOUSE = "Warehouse Inventory"
ROLE_PURCHASE_HISTORY = "Purchase History"
ROLE_SUPPLIER_PRICES = "Supplier Price Lists"


@dataclass
class CompanyRecord:
    name: str
    code: str = ""
    unit: str = ""
    warehouse_quantity: Optional[float] = None
    cost_price: Optional[float] = None
    supplier: str = ""
    source_role: str = ""
    extra: dict = field(default_factory=dict)


class CompanyDataSource(ABC):
    """A single company data source (one role)."""

    def __init__(self, role: str, name: str = ""):
        self.role = role
        self.name = name or role

    @abstractmethod
    def records(self) -> list[CompanyRecord]: ...


class InMemoryDataSource(CompanyDataSource):
    def __init__(self, role: str, records: list[CompanyRecord], name: str = ""):
        super().__init__(role, name)
        self._records = records
        for r in self._records:
            r.source_role = role

    def records(self) -> list[CompanyRecord]:
        return self._records


class CsvDataSource(CompanyDataSource):
    """Load records from a CSV.

    `column_map` maps CompanyRecord fields to CSV header names, e.g.
    {"name": "Наименование", "code": "Артикул", "warehouse_quantity": "Остаток"}.
    Anything not mapped lands in `extra`.
    """

    def __init__(self, role, path, column_map: dict, name: str = ""):
        super().__init__(role, name)
        self.path = path
        self.column_map = column_map

    def records(self) -> list[CompanyRecord]:
        out: list[CompanyRecord] = []
        with open(self.path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rec = self._row_to_record(row)
                out.append(rec)
        return out

    def _row_to_record(self, row: dict) -> CompanyRecord:
        def get(field):
            col = self.column_map.get(field)
            return row.get(col, "").strip() if col else ""

        def num(field):
            v = get(field)
            if not v:
                return None
            try:
                return float(v.replace(",", ".").replace(" ", ""))
            except ValueError:
                return None

        mapped_cols = set(self.column_map.values())
        extra = {k: v for k, v in row.items() if k not in mapped_cols}
        return CompanyRecord(
            name=get("name"),
            code=get("code"),
            unit=get("unit"),
            warehouse_quantity=num("warehouse_quantity"),
            cost_price=num("cost_price"),
            supplier=get("supplier"),
            source_role=self.role,
            extra=extra,
        )


class JsonDataSource(CompanyDataSource):
    """Load records from a JSON array of objects using a column_map (as CSV)."""

    def __init__(self, role, path, column_map: dict, name: str = ""):
        super().__init__(role, name)
        self.path = path
        self.column_map = column_map

    def records(self) -> list[CompanyRecord]:
        with open(self.path, encoding="utf-8") as f:
            data = json.load(f)
        out = []
        for row in data:

            def get(field):
                col = self.column_map.get(field)
                v = row.get(col) if col else None
                return str(v).strip() if v is not None else ""

            def num(field):
                col = self.column_map.get(field)
                v = row.get(col) if col else None
                if v in (None, ""):
                    return None
                try:
                    return float(str(v).replace(",", ".").replace(" ", ""))
                except ValueError:
                    return None

            mapped = set(self.column_map.values())
            out.append(
                CompanyRecord(
                    name=get("name"),
                    code=get("code"),
                    unit=get("unit"),
                    warehouse_quantity=num("warehouse_quantity"),
                    cost_price=num("cost_price"),
                    supplier=get("supplier"),
                    source_role=self.role,
                    extra={k: v for k, v in row.items() if k not in mapped},
                )
            )
        return out


class CompanyData:
    """Holds the four data sources and exposes them to the matcher."""

    def __init__(
        self,
        product_database: Optional[CompanyDataSource] = None,
        warehouse_inventory: Optional[CompanyDataSource] = None,
        purchase_history: Optional[CompanyDataSource] = None,
        supplier_price_lists: Optional[CompanyDataSource] = None,
    ):
        self.product_database = product_database
        self.warehouse_inventory = warehouse_inventory
        self.purchase_history = purchase_history
        self.supplier_price_lists = supplier_price_lists
        self._cache: dict[str, list[CompanyRecord]] = {}

    def get(self, source: Optional[CompanyDataSource]) -> list[CompanyRecord]:
        if source is None:
            return []
        if source.role not in self._cache:
            try:
                self._cache[source.role] = source.records()
            except Exception:
                self._cache[source.role] = []
        return self._cache[source.role]
