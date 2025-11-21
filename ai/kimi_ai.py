"""
Интеграция с OpenRouter (Moonshot AI Kimi K2) через официальный клиент OpenAI.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional

from openai import OpenAI

# Пытаемся импортировать RateLimitError, если не доступен - используем общую обработку
try:
    from openai import RateLimitError
except ImportError:
    RateLimitError = None

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
    return os.getenv("KIMI_MODEL", "moonshotai/kimi-k2:free")


def get_openrouter_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=_get_api_key(),
            base_url=_get_base_url(),
        )
        logger.info("OpenRouter клиент (Kimi) инициализирован")
    return _client


def send_chat_completion(
    messages: List[Dict[str, Any]],
    *,
    max_tokens: int = 1500,
    temperature: float = 0.7,
    persona_name: Optional[str] = None,
    enable_reasoning: bool = False,  # Kimi не поддерживает reasoning
) -> str:
    """
    Отправляет запрос к Moonshot AI Kimi K2 (OpenRouter) и возвращает текст ответа.
    Обрабатывает ошибки rate limit (429) с автоматическими повторными попытками.
    """
    client = get_openrouter_client()
    model_name = get_model_name()
    
    # Получаем site URL и title из переменных окружения (опционально)
    site_url = os.getenv("OPENROUTER_SITE_URL", "https://github.com/your-repo")
    site_name = os.getenv("OPENROUTER_SITE_NAME", "Girl-Guy.Ai Bot")
    
    extra_headers = {
        "HTTP-Referer": site_url,
        "X-Title": site_name,
    }

    # Настройки для retry при ошибке 429
    max_retries = 3
    base_delay = 2  # Начальная задержка в секундах
    
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=1,
                stream=False,
                stop=None,
                extra_headers=extra_headers,
            )

            if response.choices:
                choice = response.choices[0]
                message = choice.message
                if message and message.content:
                    content = message.content.strip()
                    if content:
                        logger.debug(
                            "Kimi ответил: %d символов, finish_reason=%s",
                            len(content),
                            choice.finish_reason,
                        )
                        return content

            logger.warning(
                "Kimi вернул пустой ответ (персонаж=%s, сообщений=%d)",
                persona_name or "-",
                len(messages),
            )
            return "Kimi ничего не ответил."

        except Exception as exc:
            # Проверяем, является ли это ошибкой rate limit (429)
            is_rate_limit = False
            if RateLimitError and isinstance(exc, RateLimitError):
                is_rate_limit = True
            else:
                error_code = getattr(exc, 'status_code', None)
                error_msg = str(exc)
                if error_code == 429 or "429" in error_msg or "rate limit" in error_msg.lower():
                    is_rate_limit = True
            
            if is_rate_limit:
                # Ошибка 429 - Too Many Requests
                if attempt < max_retries - 1:
                    # Экспоненциальная задержка: 2, 4, 8 секунд
                    delay = base_delay * (2 ** attempt)
                    logger.warning(
                        "Kimi API rate limit (429), попытка %d/%d, ждем %d сек...",
                        attempt + 1,
                        max_retries,
                        delay,
                    )
                    time.sleep(delay)
                    continue
                else:
                    # Все попытки исчерпаны
                    logger.error("Kimi API rate limit (429), все попытки исчерпаны")
                    return "⏳ Превышен лимит запросов к AI. Пожалуйста, подождите немного и попробуйте снова."
            
            # Если это не rate limit, обрабатываем как обычную ошибку (не делаем retry)
            logger.error("Ошибка Kimi API: %s", exc, exc_info=True)
            
            # Проверяем тип ошибки
            error_msg = str(exc)
            error_code = getattr(exc, 'status_code', None)
            
            # Если ошибка 403 и содержит информацию о регионе
            if error_code == 403 or "403" in error_msg or "not available in your region" in error_msg.lower():
                return "❌ Сервис Kimi недоступен в вашем регионе. Пожалуйста, используйте VPN или обратитесь к администратору."
            
            # Если ошибка содержит HTML (некорректный ответ от API)
            if "<!doctype" in error_msg.lower() or "<html>" in error_msg.lower():
                return "❌ Сервис временно недоступен. Попробуйте позже."
            
            # Общая ошибка - выходим из цикла
            break
    
    # Если все попытки исчерпаны (не должно сюда дойти, но на всякий случай)
    return "❌ Ошибка при обращении к AI. Попробуйте еще раз."


__all__ = ["send_chat_completion", "get_openrouter_client", "get_model_name"]

