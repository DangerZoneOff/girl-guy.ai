"""
Простое JSON-хранилище обработанных заказов Tribute.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional

STORE_PATH = Path(__file__).with_name("tribute_orders.json")


def _load() -> Dict[str, Dict[str, str]]:
    if not STORE_PATH.exists():
        return {}
    try:
        with STORE_PATH.open("r", encoding="utf-8") as fp:
            return json.load(fp)
    except Exception:
        return {}


def _save(data: Dict[str, Dict[str, str]]) -> None:
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with STORE_PATH.open("w", encoding="utf-8") as fp:
        json.dump(data, fp, ensure_ascii=False, indent=2)


def was_processed(order_id: str) -> bool:
    data = _load()
    return str(order_id) in data


def mark_processed(order_id: str, *, status: str = "paid", tokens: int = 0) -> None:
    data = _load()
    data[str(order_id)] = {"status": status, "tokens": tokens}
    _save(data)


