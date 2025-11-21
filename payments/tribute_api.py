"""
Асинхронный клиент Tribute API (Telegram Stars).
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://tribute.tg/api/v1"


class TributeAPIError(RuntimeError):
    pass


def _get_api_key() -> str:
    key = os.getenv("TRIBUTE_API_KEY")
    if not key:
        raise RuntimeError(
            "TRIBUTE_API_KEY не указан. Скопируй API ключ из Tribute и добавь в .env."
        )
    return key


def _get_base_url() -> str:
    return os.getenv("TRIBUTE_API_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def _build_headers() -> Dict[str, str]:
    return {
        "Api-Key": _get_api_key(),
        "Accept": "application/json",
    }


async def _request(
    method: str,
    path: str,
    *,
    params: Dict[str, Any] | None = None,
    json_payload: Dict[str, Any] | None = None,
) -> Any:
    url = f"{_get_base_url()}{path}"
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.request(
            method,
            url,
            headers=_build_headers(),
            params=params,
            json=json_payload,
        )
    if response.status_code >= 400:
        logger.error("Tribute API error %s %s: %s", method, url, response.text[:300])
        raise TributeAPIError(f"Tribute API error: {response.status_code}")
    data = response.json()
    if isinstance(data, dict) and "data" in data:
        return data["data"]
    return data


async def list_products() -> List[Dict[str, Any]]:
    """
    Возвращает список продуктов Tribute (для оплаты в звёздах).
    """
    data = await _request("GET", "/products")
    if isinstance(data, list):
        return data
    return []


async def list_product_orders(
    product_id: int, *, status: Optional[str] = None, page: int = 1, size: int = 50
) -> List[Dict[str, Any]]:
    params = {"page": page, "size": min(50, size)}
    if status:
        params["status"] = status
    data = await _request("GET", f"/products/{product_id}/orders", params=params)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        if "rows" in data and isinstance(data["rows"], list):
            return data["rows"]
    return []


async def get_order(order_id: str) -> Optional[Dict[str, Any]]:
    result = await _request("GET", f"/orders/{order_id}")
    if isinstance(result, dict):
        return result
    return None


async def list_webhooks() -> List[Dict[str, Any]]:
    data = await _request("GET", "/webhooks")
    if isinstance(data, list):
        return data
    return []


async def create_webhook(url: str, events: List[str]) -> Dict[str, Any]:
    payload = {"url": url, "events": events}
    result = await _request("POST", "/webhooks", json_payload=payload)
    if isinstance(result, dict):
        return result
    raise TributeAPIError("Unexpected webhook response")


__all__ = ["list_products", "TributeAPIError"]


