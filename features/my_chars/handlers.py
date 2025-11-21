"""
Логика кнопки «💎 Мои персонажи».
Показывает только анкеты владельца.
"""

from __future__ import annotations

from typing import Dict, List

from aiogram import Dispatcher, Bot
from aiogram.types import Message, CallbackQuery, FSInputFile, URLInputFile
from aiogram.filters import BaseFilter
from aiogram.fsm.context import FSMContext

from knops.keyboards import (
    get_reply_my_characters_menu,
    get_my_person_card_keyboard,
)
from ai.chat_state import deactivate_persona_chat
from knops.api_persons import invalidate_cache
from pers.database import update_persona
from pers.database import get_personas_by_owner, persona_to_dict, update_persona
from .delete_persona import delete_user_persona


def _truncate_caption(text: str, max_length: int = 1024) -> str:
    """
    Обрезает текст до максимальной длины для Telegram caption.
    Telegram ограничивает caption до 1024 символов.
    """
    if len(text) <= max_length:
        return text
    
    # Обрезаем текст, оставляя место для "..."
    truncated = text[:max_length - 3]
    
    # Пытаемся найти безопасное место для обрезки (не внутри HTML-тега)
    import re
    # Если обрезали внутри открывающего тега, удаляем его
    last_open_tag = re.search(r'<[^>]*$', truncated)
    if last_open_tag:
        truncated = truncated[:last_open_tag.start()]
    
    # Если обрезали внутри закрывающего тега, удаляем его
    last_close_tag = re.search(r'</[^>]*$', truncated)
    if last_close_tag:
        truncated = truncated[:last_close_tag.start()]
    
    # Простая проверка: если последний символ - это часть HTML-сущности, обрезаем дальше
    while truncated and truncated[-1] == '&':
        truncated = truncated[:-1]
    
    return truncated + "..."


def _load_profiles_for_user(user_id: int) -> List[Dict]:
    """Загружает персонажей пользователя из БД"""
    personas = get_personas_by_owner(user_id, include_public=False)
    profiles = [persona_to_dict(row) for row in personas]
    return profiles


async def _delete_last_photo_message(state: FSMContext, bot: Bot):
    """Удаляет последнее сообщение с фото, если оно есть"""
    try:
        data = await state.get_data()
        message_id = data.get("last_photo_message_id")
        chat_id = data.get("last_photo_chat_id")
        if message_id and chat_id:
            await bot.delete_message(chat_id=chat_id, message_id=message_id)
            await state.update_data(last_photo_message_id=None, last_photo_chat_id=None)
    except Exception:
        pass  # Игнорируем ошибки при удалении (сообщение уже удалено или недоступно)

async def show_my_characters(msg: Message | CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await deactivate_persona_chat(state)
    await _delete_last_photo_message(state, bot)
    
    # Обрабатываем как Message, так и CallbackQuery
    if isinstance(msg, CallbackQuery):
        await msg.answer()
        receiver = msg.message
        user_id = msg.from_user.id
    else:
        receiver = msg
        user_id = msg.from_user.id
    
    # Проверяем премиум статус
    is_premium_user = False
    try:
        from premium.subscription import is_premium
        is_premium_user = is_premium(user_id)
    except Exception:
        pass
    
    # Если нет премиума, показываем сообщение с кнопкой покупки
    if not is_premium_user:
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        builder.button(text="⭐ Купить премиум", callback_data="topup:premium")
        
        await receiver.answer(
            "❌ <b>Создание персонажей доступно только с премиум подпиской</b>\n\n"
            "Чтобы создавать своих персонажей, нужно купить премиум подписку.\n\n"
            "Премиум включает:\n"
            "✨ Неограниченное создание персонажей\n"
            "📝 Удлиненные ответы от ИИ\n"
            "💰 Токены на баланс (в зависимости от тарифа)",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        return
    
    profiles = _load_profiles_for_user(user_id)
    await receiver.answer("Мои персонажи:", reply_markup=get_reply_my_characters_menu(is_premium=is_premium_user))
    if not profiles:
        message_text = "У тебя пока нет своих персонажей.\nСоздай первого через кнопку «✨ Создать персонажа»."
        await receiver.answer(
            message_text,
            reply_markup=get_reply_my_characters_menu(is_premium=is_premium_user),
        )
        return
    await _send_profile(0, receiver, state, profiles, bot, no_prev=True)


async def my_char_next(call: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await deactivate_persona_chat(state)
    await call.answer()
    # Удаляем предыдущее сообщение с фото
    await _delete_last_photo_message(state, bot)
    user_id = call.from_user.id
    
    # Проверяем премиум статус
    is_premium_user = False
    try:
        from premium.subscription import is_premium
        is_premium_user = is_premium(user_id)
    except Exception:
        pass
    
    profiles = _load_profiles_for_user(user_id)
    if not profiles:
        await call.message.answer(
            "У тебя пока нет персонажей.",
            reply_markup=get_reply_my_characters_menu(is_premium=is_premium_user),
        )
        return
    idx = (await state.get_data()).get("my_person_index", 0)
    idx = (idx + 1) % len(profiles)
    await _send_profile(idx, call, state, profiles, bot)
    try:
        await call.message.delete()
    except Exception:
        pass


async def my_char_prev(call: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await deactivate_persona_chat(state)
    await call.answer()
    # Удаляем предыдущее сообщение с фото
    await _delete_last_photo_message(state, bot)
    user_id = call.from_user.id
    
    # Проверяем премиум статус
    is_premium_user = False
    try:
        from premium.subscription import is_premium
        is_premium_user = is_premium(user_id)
    except Exception:
        pass
    
    profiles = _load_profiles_for_user(user_id)
    if not profiles:
        await call.message.answer(
            "У тебя пока нет персонажей.",
            reply_markup=get_reply_my_characters_menu(is_premium=is_premium_user),
        )
        return
    idx = (await state.get_data()).get("my_person_index", 0)
    idx = (idx - 1 + len(profiles)) % len(profiles)
    await _send_profile(idx, call, state, profiles, bot)
    try:
        await call.message.delete()
    except Exception:
        pass


async def my_char_publish(call: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await deactivate_persona_chat(state)
    await call.answer()
    # Получаем persona_id из callback_data
    try:
        persona_id = int(call.data.split(":")[-1]) if call.data else None
    except (ValueError, IndexError):
        await call.message.answer("Не удалось определить персонажа.")
        return
    
    if persona_id is None:
        await call.message.answer("Не удалось определить персонажа.")
        return
    
    # Обновляем публичность в БД
    from pers.database import set_persona_public
    set_persona_public(persona_id, True)
    invalidate_cache()
    
    await call.message.answer("Персонаж опубликован и теперь виден всем!")
    
    user_id = call.from_user.id
    
    # Проверяем премиум статус
    is_premium_user = False
    try:
        from premium.subscription import is_premium
        is_premium_user = is_premium(user_id)
    except Exception:
        pass
    
    profiles = _load_profiles_for_user(user_id)
    if not profiles:
        await call.message.answer(
            "У тебя пока нет персонажей.",
            reply_markup=get_reply_my_characters_menu(is_premium=is_premium_user),
        )
        return
    idx = 0
    for i, profile in enumerate(profiles):
        if profile.get("id") == persona_id:
            idx = i
            break
    await _send_profile(idx, call, state, profiles, bot)


async def my_char_published_info(call: CallbackQuery) -> None:
    await call.answer("Персонаж уже опубликован.")


class EditingDescriptionFilter(BaseFilter):
    """Фильтр, проверяющий активность режима редактирования описания"""
    
    async def __call__(self, message: Message, state: FSMContext) -> bool:
        data = await state.get_data()
        return bool(data.get("editing_description_persona_id"))


async def my_char_edit_description(call: CallbackQuery, state: FSMContext) -> None:
    """Начинает редактирование описания персонажа"""
    await deactivate_persona_chat(state)
    await call.answer()
    
    # Получаем persona_id из callback_data
    try:
        persona_id = int(call.data.split(":")[-1]) if call.data else None
    except (ValueError, IndexError):
        await call.message.answer("Не удалось определить персонажа.")
        return
    
    if persona_id is None:
        await call.message.answer("Не удалось определить персонажа.")
        return
    
    # Проверяем, что персонаж принадлежит пользователю
    user_id = call.from_user.id
    profiles = _load_profiles_for_user(user_id)
    persona = None
    for p in profiles:
        if p.get("id") == persona_id:
            persona = p
            break
    
    if not persona:
        await call.message.answer("Персонаж не найден или не принадлежит вам.")
        return
    
    # Сохраняем persona_id в state для обработки ввода
    await state.update_data(editing_description_persona_id=persona_id)
    
    await call.message.answer(
        f"✏️ <b>Редактирование описания</b>\n\n"
        f"Текущее описание:\n{persona.get('description', 'Не указано')}\n\n"
        f"Введите новое описание:",
        parse_mode="HTML"
    )


async def handle_description_input(msg: Message, state: FSMContext, bot: Bot) -> None:
    """Обрабатывает ввод нового описания"""
    data = await state.get_data()
    persona_id = data.get("editing_description_persona_id")
    
    if not persona_id:
        return  # Не в режиме редактирования
    
    new_description = msg.text.strip() if msg.text else ""
    
    if not new_description:
        await msg.answer("❌ Описание не может быть пустым! Введите описание:")
        return
    
    # Обновляем описание в БД
    updated = update_persona(persona_id, description=new_description)
    
    if updated:
        invalidate_cache()
        await msg.answer("✅ Описание успешно обновлено!")
        
        # Показываем обновленную карточку персонажа
        user_id = msg.from_user.id
        profiles = _load_profiles_for_user(user_id)
        idx = 0
        for i, profile in enumerate(profiles):
            if profile.get("id") == persona_id:
                idx = i
                break
        await _send_profile(idx, msg, state, profiles, bot, no_prev=idx == 0)
    else:
        await msg.answer("❌ Не удалось обновить описание. Попробуйте позже.")
    
    # Очищаем состояние редактирования
    await state.update_data(editing_description_persona_id=None)


async def my_char_delete(call: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Удаляет персонажа пользователя"""
    await deactivate_persona_chat(state)
    await call.answer()
    
    # Получаем persona_id из callback_data
    try:
        persona_id = int(call.data.split(":")[-1]) if call.data else None
    except (ValueError, IndexError):
        await call.message.answer("Не удалось определить персонажа.")
        return
    
    if persona_id is None:
        await call.message.answer("Не удалось определить персонажа.")
        return
    
    user_id = call.from_user.id
    
    # Удаляем персонажа (с проверкой прав)
    success, message = await delete_user_persona(persona_id, user_id)
    
    if success:
        await call.message.answer(f"✅ {message}")
        
        # Проверяем премиум статус
        is_premium_user = False
        try:
            from premium.subscription import is_premium
            is_premium_user = is_premium(user_id)
        except Exception:
            pass
        
        # Обновляем список персонажей
        profiles = _load_profiles_for_user(user_id)
        if not profiles:
            message_text = "У тебя больше нет персонажей."
            if is_premium_user:
                message_text += "\nСоздай нового через кнопку «➕ Создать персонажа»."
            await call.message.answer(
                message_text,
                reply_markup=get_reply_my_characters_menu(is_premium=is_premium_user),
            )
            return
        
        # Показываем первый персонаж из списка
        await _send_profile(0, call, state, profiles, bot, no_prev=True)
        try:
            await call.message.delete()
        except Exception:
            pass
    else:
        await call.message.answer(f"❌ {message}")


async def _send_profile(
    index: int,
    receiver: Message | CallbackQuery,
    state: FSMContext,
    profiles: List[Dict],
    bot: Bot,
    no_prev: bool = False,
) -> None:
    persona = profiles[index]
    # Отображаем только имя, возраст и описание (без характера и сцены)
    text = f"<b>{persona['name']}, {persona['age']} лет</b>\n{persona['description']}"
    
    # Обрезаем текст до максимальной длины для Telegram caption (1024 символа)
    text = _truncate_caption(text, max_length=1024)
    
    persona_id = persona.get("id")
    is_published = persona.get("public", False)
    can_publish = bool(persona_id and not is_published)
    inline_markup = get_my_person_card_keyboard(
        no_prev=no_prev,
        noop=len(profiles) <= 1,
        can_publish=can_publish,
        persona_id=persona_id,  # Всегда передаем persona_id для кнопки редактирования
        published=is_published,
    )
    
    # Логика кэширования: сначала пробуем использовать file_id (Telegram не скачивает файл)
    # Если file_id невалиден - загружаем файл и обновляем file_id
    photo_file_id = persona.get("photo_file_id")
    photo_path = persona["photo"]
    sent_message = None
    
    # Проверяем, что photo_file_id не пустой и не None
    if photo_file_id and photo_file_id.strip():
        # Пробуем использовать кэшированный file_id - Telegram НЕ будет скачивать файл
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Используем кэшированный file_id для persona_id={persona_id}: {photo_file_id[:20]}...")
        try:
            if isinstance(receiver, Message):
                sent_message = await receiver.answer_photo(
                    photo_file_id,  # Передаем file_id как строку - Telegram использует кэш
                    caption=text,
                    parse_mode="HTML",
                    reply_markup=inline_markup,
                )
            else:
                sent_message = await receiver.message.answer_photo(
                    photo_file_id,  # Передаем file_id как строку - Telegram использует кэш
                    caption=text,
                    parse_mode="HTML",
                    reply_markup=inline_markup,
                )
            # file_id работает - файл НЕ скачивался, используем кэш Telegram
            logger.info(f"Успешно использован file_id для persona_id={persona_id}, файл НЕ скачивался")
        except Exception as e:
            # file_id невалиден (истек срок действия или файл удален) - загружаем файл
            logger.warning(f"file_id невалиден для persona_id={persona_id}, загружаем файл: {e}")
            photo_file_id = None  # Сбрасываем невалидный file_id
    else:
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"file_id отсутствует для persona_id={persona_id}, будет загружен файл")
    
    if not photo_file_id or not sent_message:
        # Первая отправка или file_id невалиден - загружаем файл
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Загружаем файл для persona_id={persona_id} из {photo_path[:50] if photo_path else 'N/A'}...")
        if photo_path.startswith("http://") or photo_path.startswith("https://"):
            photo = URLInputFile(photo_path)
        else:
            photo = FSInputFile(photo_path)
        
        # Отправляем фото (Telegram скачивает файл)
        if isinstance(receiver, Message):
            sent_message = await receiver.answer_photo(
                photo,
                caption=text,
                parse_mode="HTML",
                reply_markup=inline_markup,
            )
        else:
            sent_message = await receiver.message.answer_photo(
                photo,
                caption=text,
                parse_mode="HTML",
                reply_markup=inline_markup,
            )
        
        # Сохраняем file_id в БД для последующих отправок
        if persona_id and sent_message.photo:
            # Берем самое большое фото (последнее в массиве)
            new_file_id = sent_message.photo[-1].file_id
            logger.info(f"Сохраняем новый file_id для persona_id={persona_id}: {new_file_id[:20]}...")
            update_persona(persona_id, photo_file_id=new_file_id)
            # Обновляем кэш
            invalidate_cache()
    
    # Сохраняем ID сообщения с фото для последующего удаления
    if sent_message:
        await state.update_data(
            my_person_index=index,
            last_photo_message_id=sent_message.message_id,
            last_photo_chat_id=sent_message.chat.id
        )
    else:
        await state.update_data(
            my_person_index=index,
        )


def register_my_char_handlers(dp: Dispatcher) -> None:
    dp.message.register(show_my_characters, lambda m: m.text == "💎 Мои персонажи")
    dp.callback_query.register(show_my_characters, lambda c: c.data == "mychar:open")
    dp.callback_query.register(show_my_characters, lambda c: c.data == "menu:mychars")
    dp.callback_query.register(my_char_next, lambda c: c.data == "mychar:next")
    dp.callback_query.register(my_char_prev, lambda c: c.data == "mychar:prev")
    dp.callback_query.register(
        my_char_publish, lambda c: c.data and c.data.startswith("mychar:publish:")
    )
    dp.callback_query.register(my_char_published_info, lambda c: c.data == "mychar:published")
    dp.callback_query.register(
        my_char_edit_description, 
        lambda c: c.data and c.data.startswith("mychar:edit_description:")
    )
    dp.callback_query.register(
        my_char_delete,
        lambda c: c.data and c.data.startswith("mychar:delete:")
    )
    # Обработчик ввода нового описания (с фильтром)
    dp.message.register(handle_description_input, EditingDescriptionFilter())

