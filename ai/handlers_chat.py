from __future__ import annotations

import logging
from datetime import datetime

from aiogram import Bot, Dispatcher
from aiogram.filters import Command, BaseFilter
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from ai.chat import persona_context_from_dict, run_chat_turn
from ai.chat_state import deactivate_persona_chat
from ai.request_queue import get_request_lock
from SMS.tokens import consume_tokens, get_token_balance

logger = logging.getLogger(__name__)


class PersonaChatActiveFilter(BaseFilter):
    """Фильтр, проверяющий активность чата с персонажем."""
    
    async def __call__(self, message: Message, state: FSMContext) -> bool:
        data = await state.get_data()
        return bool(data.get("persona_chat_active"))


async def stop_persona_chat(msg: Message, state: FSMContext) -> None:
    if not await deactivate_persona_chat(state):
        await msg.answer("Сейчас нет активного чата с персонажем.")
        return
    
    # Очищаем блокировку при остановке чата
    user_id = msg.from_user.id
    lock = get_request_lock()
    lock.clear(user_id)
    
    await msg.answer("Чат с персонажем остановлен.")


async def _process_message(
    msg: Message, 
    state: FSMContext, 
    context_dict: dict,
    bot: Bot = None
) -> None:
    """Обрабатывает одно сообщение к ИИ."""
    context = persona_context_from_dict(context_dict)
    user_id = msg.from_user.id
    
    # Проверяем баланс токенов (но не списываем пока)
    balance = get_token_balance(user_id)
    
    # Проверяем безлимитный премиум статус
    is_unlimited = False
    try:
        from premium.subscription import is_premium_unlimited
        is_unlimited = is_premium_unlimited(user_id)
    except Exception:
        pass
    
    # Если не безлимит и баланс недостаточен - отказываем
    if not is_unlimited and balance < 1:
        await msg.answer(
            f"❗️ Недостаточно токенов. Баланс: {balance}. "
            "Нажми «💰 Пополнить баланс» или используй команду /topup.",
        )
        return
    
    # Отмечаем начало обработки
    lock = get_request_lock()
    lock.start_request(user_id)
    
    # Флаг, были ли списаны токены
    tokens_consumed = False
    
    try:
        # Отправляем запрос к ИИ в отдельном потоке, чтобы не блокировать event loop
        # Это позволяет обрабатывать запросы от разных пользователей параллельно
        import asyncio
        response, updated_context = await asyncio.to_thread(run_chat_turn, context, msg.text or "")
        
        # Проверяем, является ли ответ ошибкой
        # Ошибки обычно начинаются с ❌ или ⏳, или содержат определенные фразы
        is_error = (
            response.startswith("❌") or 
            response.startswith("⏳") or
            "ошибка" in response.lower() or
            "недоступен" in response.lower() or
            "попробуйте позже" in response.lower() or
            "попробуйте еще раз" in response.lower() or
            "временно недоступен" in response.lower() or
            "не работает" in response.lower()
        )
        
        # Списываем токены ТОЛЬКО если ответ успешный (не ошибка)
        if not is_unlimited and not is_error:
            if consume_tokens(user_id, 1):
                tokens_consumed = True
                logger.info(f"Токены списаны после успешного ответа для user_id={user_id}")
            else:
                logger.warning(f"Не удалось списать токены для user_id={user_id} после успешного ответа")
        elif is_error:
            logger.info(f"Токены НЕ списаны для user_id={user_id} - ответ содержит ошибку")
        
        # Обновляем контекст
        updated_context_dict = updated_context.to_dict()
        await state.update_data(persona_chat_context=updated_context_dict)
        
        # Проверяем, содержит ли ответ HTML теги (может быть ошибка от API)
        # Если содержит HTML теги типа <!doctype, <html>, <script> - отправляем без parse_mode
        contains_html_error = any(tag in response.lower() for tag in ["<!doctype", "<html>", "<script>"])
        
        # Отправляем ответ
        try:
            if bot:
                if contains_html_error:
                    await bot.send_message(chat_id=user_id, text=response)
                else:
                    await bot.send_message(chat_id=user_id, text=response, parse_mode="HTML")
            else:
                if contains_html_error:
                    await msg.answer(response)
                else:
                    await msg.answer(response, parse_mode="HTML")
        except Exception as send_error:
            # Если ошибка парсинга HTML - отправляем без parse_mode
            logger.warning(f"Ошибка отправки с HTML парсингом, отправляем без parse_mode: {send_error}")
            if bot:
                await bot.send_message(chat_id=user_id, text=response)
            else:
                await msg.answer(response)
    except Exception as e:
        logger.error(f"Ошибка при обработке сообщения {msg.message_id}: {e}", exc_info=True)
        
        # Если токены были списаны, но произошла ошибка - возвращаем их
        if tokens_consumed:
            from SMS.tokens import add_tokens
            add_tokens(user_id, 1)
            logger.info(f"Токены возвращены user_id={user_id} из-за ошибки обработки")
        
        await msg.answer("Произошла ошибка при обработке сообщения. Попробуйте еще раз.")
    finally:
        # Всегда снимаем блокировку после обработки
        lock.finish_request(user_id)


async def handle_persona_chat_message(msg: Message, state: FSMContext, bot: Bot) -> None:
    """Обрабатывает сообщение в чате с персонажем с блокировкой повторных запросов."""
    data = await state.get_data()
    context_dict = data.get("persona_chat_context")
    if not context_dict:
        await state.update_data(persona_chat_active=False)
        await msg.answer("Контекст чата потерян. Нажми «Начать чат», чтобы создать новый.")
        return
    
    user_id = msg.from_user.id
    lock = get_request_lock()
    
    # Проверяем, есть ли активный запрос
    if lock.has_active_request(user_id):
        # Есть активный запрос - просто игнорируем сообщение
        logger.info(f"Сообщение {msg.message_id} игнорируется для user_id={user_id} (есть активный запрос)")
        return
    
    # Нет активного запроса - обрабатываем сразу
    await _process_message(msg, state, context_dict, bot)


def register_chat_handlers(dp: Dispatcher) -> None:
    # Регистрируем хэндлер чата с фильтром и высоким приоритетом, чтобы он обрабатывался раньше FSM хэндлеров
    dp.message.register(handle_persona_chat_message, PersonaChatActiveFilter())
    dp.message.register(stop_persona_chat, Command("stopchat"))

