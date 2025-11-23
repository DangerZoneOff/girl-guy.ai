"""
Интеграция с NVIDIA API (DeepSeek V3.1 Terminus) через официальный клиент OpenAI.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from openai import OpenAI

logger = logging.getLogger(__name__)
_client: OpenAI | None = None


def _get_api_key() -> str:
    # API ключ встроен в код
    api_key = "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"
    
    # Также проверяем переменную окружения (если нужно переопределить)
    env_key = os.getenv("NVIDIA_API_KEY")
    if env_key:
        api_key = env_key.strip()
        # Удаляем возможные кавычки, если они есть
        if api_key.startswith('"') and api_key.endswith('"'):
            api_key = api_key[1:-1]
        if api_key.startswith("'") and api_key.endswith("'"):
            api_key = api_key[1:-1]
    
    return api_key


def _get_base_url() -> str:
    base_url = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
    # Убеждаемся, что URL - это строка без проблем с кодировкой
    if isinstance(base_url, bytes):
        base_url = base_url.decode('utf-8')
    return str(base_url).strip()


def get_model_name() -> str:
    return os.getenv("DEEPSEEK_MODEL", "deepseek-ai/deepseek-v3.1-terminus")


def get_nvidia_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = _get_api_key()
        base_url = _get_base_url()
        
        # Убеждаемся, что ключ и URL не содержат проблемных символов
        # Проверяем, что это ASCII-совместимые строки для заголовков HTTP
        try:
            api_key.encode('ascii')
            base_url.encode('ascii')
        except UnicodeEncodeError as e:
            logger.error(f"API ключ или base_url содержат не-ASCII символы: {e}")
            # Пытаемся очистить от не-ASCII символов
            api_key = api_key.encode('ascii', 'ignore').decode('ascii')
            base_url = base_url.encode('ascii', 'ignore').decode('ascii')
        
        # Удаляем возможные невидимые символы и пробелы
        api_key = ''.join(c for c in api_key if c.isprintable() or c.isspace()).strip()
        base_url = ''.join(c for c in base_url if c.isprintable() or c.isspace()).strip()
        
        # Логируем первые и последние символы ключа для отладки (без показа самого ключа)
        if api_key:
            logger.debug(f"API ключ загружен, длина: {len(api_key)}, начинается с: {api_key[:3]}..., заканчивается на: ...{api_key[-3:]}")
        else:
            logger.error("API ключ пустой после обработки!")
        
        # Создаем клиент с явным указанием параметров
        # Используем только ASCII-совместимые строки
        _client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=60.0,  # Явно указываем timeout
        )
        logger.info("NVIDIA клиент (DeepSeek) инициализирован")
    return _client


def send_chat_completion(
    messages: List[Dict[str, Any]],
    *,
    max_tokens: int = 1500,
    temperature: float = 0.2,
    persona_name: Optional[str] = None,
    enable_reasoning: bool = True,  # DeepSeek поддерживает reasoning
) -> str:
    """
    Отправляет запрос к DeepSeek V3.1 Terminus (NVIDIA API) и возвращает текст ответа.
    Поддерживает reasoning (мышление модели).
    """
    client = get_nvidia_client()
    model_name = get_model_name()

    try:
        # Настройки для reasoning
        extra_body: Dict[str, Any] | None = None
        if enable_reasoning:
            extra_body = {"chat_template_kwargs": {"thinking": True}}

        # Убеждаемся, что model_name - это строка без проблем с кодировкой
        model_name_str = str(model_name).strip()
        
        # Используем stream=False для совместимости с роутером
        # Если нужно streaming, можно будет добавить отдельную функцию
        response = client.chat.completions.create(
            model=model_name_str,
            messages=messages,
            temperature=temperature,
            top_p=0.7,
            max_tokens=max_tokens,
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
                        "DeepSeek ответил: %d символов, finish_reason=%s",
                        len(content),
                        choice.finish_reason,
                    )
                    return content

        logger.warning(
            "DeepSeek вернул пустой ответ (персонаж=%s, сообщений=%d)",
            persona_name or "-",
            len(messages),
        )
        return "DeepSeek ничего не ответил."

    except Exception as exc:
        logger.error("Ошибка DeepSeek API: %s", exc, exc_info=True)
        
        # Проверяем тип ошибки
        error_msg = str(exc)
        error_code = getattr(exc, 'status_code', None)
        
        # Ошибка 401 - неверный API ключ
        if error_code == 401 or "401" in error_msg or "unauthorized" in error_msg.lower() or "authentication failed" in error_msg.lower():
            logger.error("Ошибка аутентификации DeepSeek: проверьте NVIDIA_API_KEY в .env")
            return "❌ Ошибка аутентификации DeepSeek. Проверьте NVIDIA_API_KEY в .env файле."
        
        # Если ошибка 403 и содержит информацию о регионе
        if error_code == 403 or "403" in error_msg or "not available in your region" in error_msg.lower():
            return "❌ Сервис DeepSeek недоступен в вашем регионе. Пожалуйста, используйте VPN или обратитесь к администратору."
        
        # Если ошибка содержит HTML (некорректный ответ от API)
        if "<!doctype" in error_msg.lower() or "<html>" in error_msg.lower():
            return "❌ Сервис временно недоступен. Попробуйте позже."
        
        # Общая ошибка
        return "❌ Ошибка при обращении к AI. Попробуйте еще раз."


__all__ = ["send_chat_completion", "get_nvidia_client", "get_model_name"]

