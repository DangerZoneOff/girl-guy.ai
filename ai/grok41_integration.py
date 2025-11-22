"""
Интеграция с OpenRouter (Grok 4.1) через официальный клиент OpenAI.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from openai import OpenAI

logger = logging.getLogger(__name__)
_client: OpenAI | None = None


def _get_api_key() -> str:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Не указан API-ключ OpenRouter (OPENROUTER_API_KEY). Добавьте его в .env."
        )
    return api_key


def _get_base_url() -> str:
    return os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")


def get_model_name() -> str:
    return os.getenv("OPENROUTER_MODEL", "x-ai/grok-4.1-fast")


def get_openrouter_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=_get_api_key(),
            base_url=_get_base_url(),
        )
        logger.info("OpenRouter клиент инициализирован")
    return _client


def send_chat_completion(
    messages: List[Dict[str, Any]],
    *,
    max_tokens: int = 1500,
    temperature: float = 0.7,
    persona_name: Optional[str] = None,
    enable_reasoning: bool = True,
) -> str:
    """
    Отправляет запрос к Grok 4.1 (OpenRouter) и возвращает текст ответа.
    Теперь используется через роутер моделей с автоматическим fallback.
    """
    client = get_openrouter_client()
    model_name = get_model_name()

    extra_body: Dict[str, Any] | None = None
    if enable_reasoning:
        extra_body = {"reasoning": {"enabled": True}}

    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=1,
            stream=False,
            stop=None,
            extra_body=extra_body,
        )

        if response.choices:
            choice = response.choices[0]
            message = choice.message
            if message and message.content:
                content = message.content.strip()
                if content:
                    logger.debug(
                        "Grok ответил: %d символов, finish_reason=%s",
                        len(content),
                        choice.finish_reason,
                    )
                    return content

        logger.warning(
            "Grok вернул пустой ответ (персонаж=%s, сообщений=%d)",
            persona_name or "-",
            len(messages),
        )
        return "Grok ничего не ответил."

    except Exception as exc:
        logger.error("Ошибка Grok API: %s", exc, exc_info=True)
        
        # Проверяем тип ошибки
        error_msg = str(exc)
        
        # Если ошибка 403 и содержит информацию о регионе
        if "403" in error_msg or "not available in your region" in error_msg.lower():
            return "❌ Сервис Grok недоступен в вашем регионе. Пожалуйста, используйте VPN или обратитесь к администратору."
        
        # Если ошибка содержит HTML (некорректный ответ от API)
        if "<!doctype" in error_msg.lower() or "<html>" in error_msg.lower():
            return "❌ Сервис временно недоступен. Попробуйте позже."
        
        # Общая ошибка
        return "❌ Ошибка при обращении к AI. Попробуйте еще раз."


__all__ = ["send_chat_completion", "get_openrouter_client", "get_model_name"]


