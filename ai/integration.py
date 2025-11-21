"""
Интеграция с Mistral AI через официальный SDK.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from mistralai import Mistral

DEFAULT_API_KEY = "2qM4vJGl1C0RH1Zwx8p50EH1HusFxzpf"
# Используем Mistral Medium
DEFAULT_MODEL_NAME = os.getenv("MISTRAL_MODEL", "mistral-medium-latest")

_client: Mistral | None = None
logger = logging.getLogger(__name__)


def _get_api_key() -> str:
    api_key = os.getenv("MISTRAL_API_KEY", DEFAULT_API_KEY)
    if not api_key:
        raise RuntimeError("Не указан API-ключ Mistral (MISTRAL_API_KEY).")
    return api_key


def get_model_name() -> str:
    return os.getenv("MISTRAL_MODEL", DEFAULT_MODEL_NAME)


def get_mistral_client() -> Mistral:
    global _client
    if _client is None:
        _client = Mistral(api_key=_get_api_key())
    return _client


def send_chat_completion(
    messages: List[Dict[str, Any]],
    *,
    max_tokens: int = 1000,  # Увеличено для более полных и связных ответов
    temperature: float = 0.7,  # Снижено для более стабильных и связных ответов (меньше случайности)
    persona_name: Optional[str] = None,
) -> str:
    """
    ЗАГЛУШКА: Mistral AI отключен. Используется Groq (moonshotai/kimi-k2-instruct-0905).
    Эта функция больше не используется, оставлена для совместимости.
    """
    logger.warning(
        "Попытка использовать отключенный Mistral AI. Используйте ai.groq_integration вместо ai.integration"
    )
    return "Mistral AI отключен. Используется Groq."


__all__ = ["send_chat_completion", "get_mistral_client", "get_model_name"]
