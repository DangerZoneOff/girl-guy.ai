"""
Менеджер моделей с автоматической ротацией и fallback.
Выбирает рабочую модель на основе недавнего использования и статуса.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ModelStatus:
    """Статус модели."""
    name: str
    is_working: bool = True  # Работает ли модель сейчас
    last_success_time: float = 0.0  # Время последнего успешного запроса
    last_failure_time: float = 0.0  # Время последней ошибки
    consecutive_failures: int = 0  # Количество последовательных ошибок
    total_requests: int = 0  # Всего запросов
    total_successes: int = 0  # Успешных запросов


@dataclass
class ModelProvider:
    """Провайдер модели."""
    name: str
    send_function: Callable  # Функция send_chat_completion
    status: ModelStatus = field(default_factory=lambda: None)
    priority: int = 0  # Приоритет (чем выше, тем раньше выбирается)
    enabled: bool = True  # Включена ли модель


class ModelRouter:
    """
    Роутер моделей с автоматическим fallback и приоритизацией.
    Выбирает модель на основе:
    1. Недавнего успешного использования (приоритет)
    2. Статуса работоспособности
    3. Количества последовательных ошибок
    """
    
    def __init__(self):
        self.models: List[ModelProvider] = []
        self._last_cleanup_time = time.time()
        self._cleanup_interval = 300  # Очистка статуса каждые 5 минут
        
    def register_model(
        self,
        name: str,
        send_function: Callable,
        priority: int = 0,
        enabled: bool = True,
    ) -> None:
        """
        Регистрирует новую модель.
        
        Args:
            name: Имя модели (для логирования)
            send_function: Функция send_chat_completion из интеграции
            priority: Приоритет (чем выше, тем раньше выбирается)
            enabled: Включена ли модель
        """
        status = ModelStatus(name=name)
        provider = ModelProvider(
            name=name,
            send_function=send_function,
            status=status,
            priority=priority,
            enabled=enabled,
        )
        self.models.append(provider)
        logger.info(f"Зарегистрирована модель: {name} (приоритет: {priority}, включена: {enabled})")
    
    def _get_available_models(self) -> List[ModelProvider]:
        """Возвращает список доступных моделей, отсортированный по приоритету."""
        available = [m for m in self.models if m.enabled]
        
        # Сортируем по приоритету и времени последнего успеха
        def sort_key(model: ModelProvider) -> tuple:
            # Приоритет (выше = лучше)
            priority_score = model.priority
            
            # Бонус за недавний успех (время в секундах с последнего успеха)
            # Модели, которые работали недавно, получают бонус
            time_since_success = time.time() - model.status.last_success_time
            # Если успех был недавно (менее 10 минут), даем бонус
            recent_success_bonus = 1000 if time_since_success < 600 else 0
            
            # Штраф за последовательные ошибки
            failure_penalty = model.status.consecutive_failures * 100
            
            # Штраф за неработающую модель
            working_bonus = 500 if model.status.is_working else 0
            
            return (
                -(priority_score + recent_success_bonus + working_bonus - failure_penalty),  # Отрицательный для обратной сортировки
                time_since_success,  # Второй ключ - время с последнего успеха
            )
        
        available.sort(key=sort_key)
        return available
    
    def _mark_success(self, model: ModelProvider) -> None:
        """Отмечает успешный запрос к модели."""
        model.status.is_working = True
        model.status.last_success_time = time.time()
        model.status.consecutive_failures = 0
        model.status.total_requests += 1
        model.status.total_successes += 1
    
    def _mark_failure(self, model: ModelProvider) -> None:
        """Отмечает неудачный запрос к модели."""
        model.status.last_failure_time = time.time()
        model.status.consecutive_failures += 1
        model.status.total_requests += 1
        
        # Если слишком много ошибок подряд, помечаем как неработающую
        if model.status.consecutive_failures >= 3:
            model.status.is_working = False
            logger.warning(
                f"Модель {model.name} помечена как неработающая "
                f"(ошибок подряд: {model.status.consecutive_failures})"
            )
    
    def _cleanup_statuses(self) -> None:
        """Периодически очищает статусы моделей (сбрасывает флаги неработающих)."""
        current_time = time.time()
        if current_time - self._last_cleanup_time < self._cleanup_interval:
            return
        
        self._last_cleanup_time = current_time
        
        for model in self.models:
            # Если модель была помечена как неработающая, но прошло достаточно времени,
            # даем ей еще один шанс
            if not model.status.is_working:
                time_since_failure = current_time - model.status.last_failure_time
                if time_since_failure > 600:  # 10 минут
                    logger.info(f"Сбрасываем статус неработающей модели {model.name} (прошло {time_since_failure:.0f} сек)")
                    model.status.is_working = True
                    model.status.consecutive_failures = 0
    
    def send_chat_completion(
        self,
        messages: List[Dict[str, Any]],
        *,
        max_tokens: int = 1500,
        temperature: float = 0.7,
        persona_name: Optional[str] = None,
        enable_reasoning: bool = False,
    ) -> str:
        """
        Отправляет запрос к моделям с автоматическим fallback.
        Пробует модели по приоритету, переключается на следующую при ошибке.
        
        Returns:
            Ответ от модели или сообщение об ошибке, если все модели недоступны.
        """
        self._cleanup_statuses()
        
        available_models = self._get_available_models()
        
        if not available_models:
            logger.error("Нет доступных моделей")
            return "❌ Нет доступных моделей AI. Обратитесь к администратору."
        
        errors = []
        
        # Настройки для повторных попыток
        max_retries_per_model = 3  # Количество попыток для каждой модели
        retry_delay = 10  # Задержка между попытками в секундах
        
        # Пробуем модели по приоритету
        for model in available_models:
            logger.debug(f"Пробуем модель: {model.name}")
            
            # Делаем до 3 попыток для каждой модели
            for attempt in range(max_retries_per_model):
                try:
                    if attempt > 0:
                        logger.info(f"Повторная попытка {attempt + 1}/{max_retries_per_model} для модели {model.name}")
                    
                    # Вызываем функцию модели
                    response = model.send_function(
                        messages=messages,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        persona_name=persona_name,
                        enable_reasoning=enable_reasoning,
                    )
                    
                    # Проверяем, что ответ не является сообщением об ошибке
                    if response and not response.startswith("❌") and not response.startswith("⏳"):
                        # Успех!
                        self._mark_success(model)
                        if attempt > 0:
                            logger.info(f"Успешный запрос к модели {model.name} после {attempt + 1} попытки")
                        else:
                            logger.info(f"Успешный запрос к модели {model.name}")
                        return response
                    else:
                        # Ответ содержит ошибку
                        if attempt < max_retries_per_model - 1:
                            # Есть еще попытки - ждем и повторяем
                            logger.warning(
                                f"Модель {model.name} вернула ошибку (попытка {attempt + 1}/{max_retries_per_model}): {response}. "
                                f"Повторная попытка через {retry_delay} сек..."
                            )
                            time.sleep(retry_delay)
                            continue
                        else:
                            # Все попытки исчерпаны для этой модели
                            self._mark_failure(model)
                            errors.append(f"{model.name}: {response}")
                            logger.warning(f"Модель {model.name} не ответила после {max_retries_per_model} попыток: {response}")
                            break  # Переходим к следующей модели
                        
                except Exception as exc:
                    # Исключение при вызове модели
                    if attempt < max_retries_per_model - 1:
                        # Есть еще попытки - ждем и повторяем
                        logger.warning(
                            f"Ошибка при запросе к модели {model.name} (попытка {attempt + 1}/{max_retries_per_model}): {exc}. "
                            f"Повторная попытка через {retry_delay} сек..."
                        )
                        time.sleep(retry_delay)
                        continue
                    else:
                        # Все попытки исчерпаны для этой модели
                        self._mark_failure(model)
                        error_msg = str(exc)
                        errors.append(f"{model.name}: {error_msg}")
                        logger.error(f"Модель {model.name} не ответила после {max_retries_per_model} попыток: {exc}", exc_info=True)
                        break  # Переходим к следующей модели
        
        # Все модели не сработали
        logger.error(f"Все модели не сработали. Ошибки: {errors}")
        return "❌ Все модели AI временно недоступны. Попробуйте позже."
    
    def get_status(self) -> Dict[str, Any]:
        """Возвращает статус всех моделей для отладки."""
        return {
            model.name: {
                "enabled": model.enabled,
                "is_working": model.status.is_working,
                "last_success": model.status.last_success_time,
                "last_failure": model.status.last_failure_time,
                "consecutive_failures": model.status.consecutive_failures,
                "total_requests": model.status.total_requests,
                "total_successes": model.status.total_successes,
                "success_rate": (
                    model.status.total_successes / model.status.total_requests
                    if model.status.total_requests > 0
                    else 0.0
                ),
            }
            for model in self.models
        }


# Глобальный экземпляр роутера
_router: ModelRouter | None = None


def get_router() -> ModelRouter:
    """Возвращает глобальный экземпляр роутера."""
    global _router
    if _router is None:
        _router = ModelRouter()
        _initialize_models(_router)
    return _router


def _initialize_models(router: ModelRouter) -> None:
    """
    Инициализирует все доступные модели.
    
    Чтобы добавить новую модель:
    1. Создайте файл интеграции (например, ai/new_model_integration.py)
    2. Реализуйте функцию send_chat_completion с такой же сигнатурой
    3. Добавьте регистрацию здесь:
       
       try:
           from ai.new_model_integration import send_chat_completion as new_model_send
           router.register_model("Название модели", new_model_send, priority=50, enabled=True)
       except Exception as e:
           logger.warning(f"Не удалось зарегистрировать новую модель: {e}")
    
    Приоритеты:
    - Чем выше priority, тем раньше выбирается модель
    - Рекомендуется: лучшие модели = 100, хорошие = 80-90, запасные = 50-70
    """
    
    # Регистрируем модели с приоритетами
    # Чем выше приоритет, тем раньше выбирается модель
    
    # Gemini 3 Pro - первая модель (наивысший приоритет)
    try:
        from ai.gemini3pro_integration import send_chat_completion as gemini3pro_send
        router.register_model("Gemini 3 Pro (ZenMux)", gemini3pro_send, priority=150, enabled=True)
    except Exception as e:
        logger.warning(f"Не удалось зарегистрировать Gemini 3 Pro: {e}")
    
    # DeepSeek - вторая модель
    try:
        from ai.deepseek_integration import send_chat_completion as deepseek_send
        router.register_model("DeepSeek V3.1 Terminus (NVIDIA)", deepseek_send, priority=100, enabled=True)
    except Exception as e:
        logger.warning(f"Не удалось зарегистрировать DeepSeek: {e}")
    
    try:
        from ai.gemini_integration import send_chat_completion as gemini_send
        router.register_model("Gemini 2.0 Flash (OpenRouter)", gemini_send, priority=80, enabled=True)
    except Exception as e:
        logger.warning(f"Не удалось зарегистрировать Gemini 2.0: {e}")
    
    try:
        from ai.grok41_integration import send_chat_completion as grok_send
        router.register_model("Grok 4.1 (OpenRouter)", grok_send, priority=70, enabled=True)
    except Exception as e:
        logger.warning(f"Не удалось зарегистрировать Grok: {e}")
    
    try:
        from ai.kimi_ai import send_chat_completion as kimi_send
        router.register_model("Kimi K2 (OpenRouter)", kimi_send, priority=60, enabled=True)
    except Exception as e:
        logger.warning(f"Не удалось зарегистрировать Kimi: {e}")


def send_chat_completion(
    messages: List[Dict[str, Any]],
    *,
    max_tokens: int = 1500,
    temperature: float = 0.7,
    persona_name: Optional[str] = None,
    enable_reasoning: bool = False,
) -> str:
    """
    Главная функция для отправки запросов к AI.
    Автоматически выбирает рабочую модель с fallback.
    """
    router = get_router()
    return router.send_chat_completion(
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
        persona_name=persona_name,
        enable_reasoning=enable_reasoning,
    )


__all__ = ["send_chat_completion", "get_router", "ModelRouter"]

