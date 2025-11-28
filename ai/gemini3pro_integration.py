"""
Интеграция с ZenMux (Google Gemini 3 Pro) через официальный клиент OpenAI.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from openai import OpenAI

logger = logging.getLogger(__name__)
_client: OpenAI | None = None


def _get_api_key() -> str:
    api_key = os.getenv("ZENMUX_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Не указан API-ключ ZenMux (ZENMUX_API_KEY). Добавьте его в .env."
        )
    return api_key


def _get_base_url() -> str:
    return os.getenv("ZENMUX_BASE_URL", "https://zenmux.ai/api/v1")


def get_model_name() -> str:
    return os.getenv("ZENMUX_MODEL", "google/gemini-3-pro-preview-free")


def get_zenmux_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=_get_api_key(),
            base_url=_get_base_url(),
            max_retries=0,  # Отключаем автоматические повторные попытки библиотеки
        )
        logger.info("ZenMux клиент (Gemini 3 Pro) инициализирован")
    return _client


def send_chat_completion(
    messages: List[Dict[str, Any]],
    *,
    max_tokens: int = 1500,
    temperature: float = 0.7,
    persona_name: Optional[str] = None,
    enable_reasoning: bool = False,  # Gemini не поддерживает reasoning
) -> str:
    """
    Отправляет запрос к Google Gemini 3 Pro (ZenMux) и возвращает текст ответа.
    """
    client = get_zenmux_client()
    model_name = get_model_name()

    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=1,
            stream=False,
            stop=None,
        )

        if response.choices:
            choice = response.choices[0]
            message = choice.message
            if message and message.content:
                content = message.content.strip()
                if content:
                    logger.debug(
                        "Gemini 3 Pro ответил: %d символов, finish_reason=%s",
                        len(content),
                        choice.finish_reason,
                    )
                    return content

        logger.warning(
            "Gemini 3 Pro вернул пустой ответ (персонаж=%s, сообщений=%d)",
            persona_name or "-",
            len(messages),
        )
        return "Gemini 3 Pro ничего не ответил."

    except Exception as exc:
        logger.error("Ошибка Gemini 3 Pro API: %s", exc, exc_info=True)
        
        # Проверяем тип ошибки
        error_msg = str(exc)
        
        # Если ошибка 403 и содержит информацию о регионе
        if "403" in error_msg or "not available in your region" in error_msg.lower():
            return "❌ Сервис Gemini 3 Pro недоступен в вашем регионе. Пожалуйста, используйте VPN или обратитесь к администратору."
        
        # Если ошибка содержит HTML (некорректный ответ от API)
        if "<!doctype" in error_msg.lower() or "<html>" in error_msg.lower():
            return "❌ Сервис временно недоступен. Попробуйте позже."
        
        # Общая ошибка
        return "❌ Ошибка при обращении к AI. Попробуйте еще раз."


__all__ = ["send_chat_completion", "get_zenmux_client", "get_model_name"]

