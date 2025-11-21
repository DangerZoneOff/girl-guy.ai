from aiogram import Dispatcher, Bot
from aiogram.types import CallbackQuery, Message, FSInputFile, URLInputFile, InputFile
from aiogram.fsm.context import FSMContext
import datetime
from .keyboards import (
    get_reply_main_menu,
    get_reply_section_menu,
    get_reply_characters_menu,
    get_person_card_keyboard,
)
from .user_profiles import get_registration_date
from SMS.tokens import get_token_balance, consume_tokens
from knops.api_persons import list_profiles, invalidate_cache
from features.my_chars.handlers import register_my_char_handlers
from admin import is_admin, delete_persona
from ai.chat import start_persona_chat, build_persona_intro, format_persona_response
from ai.chat_state import deactivate_persona_chat
from pers.database import update_persona, increment_persona_chat_count


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

async def profile_menu_handler(msg: Message | CallbackQuery, state: FSMContext, bot: Bot):
    """
    Выводит реальный профиль пользователя: username, id, баланс, регистрация.
    """
    await deactivate_persona_chat(state)
    await _delete_last_photo_message(state, bot)
    
    # Обрабатываем как Message, так и CallbackQuery
    if isinstance(msg, CallbackQuery):
        await msg.answer()
        receiver = msg.message
        user = msg.from_user
    else:
        receiver = msg
        user = msg.from_user
    
    username = user.username or f"id{user.id}"
    reg_date = get_registration_date(user.id) or "-"
    
    # Проверяем премиум статус
    premium_active = False
    premium_text = ""
    try:
        from premium.subscription import is_premium, get_premium_expiry, get_premium_status, is_premium_unlimited
        premium_active = is_premium(user.id)
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Профиль user_id={user.id}: premium_active={premium_active}")
        
        if premium_active:
            expiry = get_premium_expiry(user.id)
            status = get_premium_status(user.id)
            unlimited = is_premium_unlimited(user.id)
            
            logger.info(f"Профиль user_id={user.id}: expiry={expiry}, status={status}, unlimited={unlimited}")
            
            if expiry:
                expiry_str = expiry.strftime("%d.%m.%Y")
                premium_text = f"\n⭐ <b>Премиум активен</b> до {expiry_str}"
            else:
                premium_text = "\n⭐ <b>Премиум активен</b>"
        else:
            premium_text = ""  # Не показываем ничего, если премиум не активен
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Ошибка при проверке премиум статуса в профиле для user_id={user.id}: {e}", exc_info=True)
        premium_text = ""
        premium_active = False
    
    # Формируем текст баланса
    if premium_active:
        try:
            from premium.subscription import is_premium_unlimited
            if is_premium_unlimited(user.id):
                balance_text = "♾️ Токены: <b>бесконечные</b> (премиум)"
            else:
                balance = get_token_balance(user.id)
                balance_text = f"💰 Баланс: {balance} токенов"
        except Exception:
            balance = get_token_balance(user.id)
            balance_text = f"💰 Баланс: {balance} токенов"
    else:
        balance = get_token_balance(user.id)
        balance_text = f"💰 Баланс: {balance} токенов"
    
    # Формируем текст профиля
    text = (
        "✨ Профиль\n\n"
        f"👤 Username: @{username}\n"
        f"🆔 ID: {user.id}\n"
        f"{balance_text}\n"
        f"📅 Регистрация: {reg_date}"
    )
    
    # Добавляем информацию о премиум в конец (если активен) или строку о пополнении (если не активен)
    if premium_active:
        text += premium_text
    else:
        text += "\n\n"
        text += "Чтобы пополнить баланс, нажми «💰 Пополнить баланс»."
    
    await receiver.answer(text, reply_markup=get_reply_section_menu(), parse_mode="HTML")

async def send_person_card(index, receiver, state, bot: Bot, no_prev=False):
    profiles = list_profiles()
    if not profiles:
        await receiver.answer("Нет ни одного персонажа.")
        return
    if index < 0 or index >= len(profiles):
        index = 0
    persona = profiles[index]
    # В анкете показываем только имя, возраст и описание (если есть)
    # Характер, Сцена и Начальная сцена используются только для AI, но не показываются в анкете
    text = f"<b>{persona['name']}, {persona['age']} лет</b>"
    description = persona.get('description')
    if description:
        text += f"\n{description}"
    
    # Обрезаем текст до максимальной длины для Telegram caption (1024 символа)
    text = _truncate_caption(text, max_length=1024)
    
    persona_id = persona.get("id")
    user_id = receiver.from_user.id  # Message и CallbackQuery имеют from_user
    markup = get_person_card_keyboard(
        no_prev=no_prev,
        module_file=None,  # Больше не используется, оставлено для совместимости
        can_delete=bool(persona_id and is_admin(user_id)),
        can_chat=bool(persona_id),
        person_index=index,  # Используем индекс вместо полного пути
    )
    
    # Логика кэширования: сначала пробуем использовать file_id (Telegram не скачивает файл)
    # Если file_id невалиден - загружаем файл и обновляем file_id
    photo_file_id = persona.get("photo_file_id")
    photo_path = persona['photo']
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
                    parse_mode='HTML',
                    reply_markup=markup
                )
            else:
                sent_message = await receiver.message.answer_photo(
                    photo_file_id,  # Передаем file_id как строку - Telegram использует кэш
                    caption=text,
                    parse_mode='HTML',
                    reply_markup=markup
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
        logger.info(f"Загружаем файл для persona_id={persona_id} из {photo_path[:50]}...")
        if photo_path.startswith("http://") or photo_path.startswith("https://"):
            photo = URLInputFile(photo_path)
        else:
            photo = FSInputFile(photo_path)
        
        # Отправляем фото (Telegram скачивает файл)
        if isinstance(receiver, Message):
            sent_message = await receiver.answer_photo(photo, caption=text, parse_mode='HTML', reply_markup=markup)
        else:
            sent_message = await receiver.message.answer_photo(photo, caption=text, parse_mode='HTML', reply_markup=markup)
        
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
            person_index=index,
            last_photo_message_id=sent_message.message_id,
            last_photo_chat_id=sent_message.chat.id
        )
    else:
        await state.update_data(person_index=index)

async def popular_menu_handler(msg: Message | CallbackQuery, state: FSMContext, bot: Bot):
    """Обработчик кнопки 'Популярные Персонажи'."""
    await deactivate_persona_chat(state)
    await _delete_last_photo_message(state, bot)
    
    # Обрабатываем как Message, так и CallbackQuery
    if isinstance(msg, CallbackQuery):
        await msg.answer()
        receiver = msg.message
    else:
        receiver = msg
    
    profiles = list_profiles()
    if not profiles:
        await receiver.answer("Нет ни одного персонажа.", reply_markup=get_reply_main_menu())
        return
    await receiver.answer(
        "⭐ Популярные Персонажи",
        reply_markup=get_reply_characters_menu(),
    )
    await send_person_card(0, receiver, state, bot, no_prev=True)

async def back_menu_handler(msg: Message, state: FSMContext, bot: Bot):
    await deactivate_persona_chat(state)
    await _delete_last_photo_message(state, bot)
    await msg.answer("Вы вернулись в главное меню", reply_markup=get_reply_main_menu())

# --- CALLBACK HANDLERS ---
async def character_next_callback(call: CallbackQuery, state: FSMContext, bot: Bot):
    # Отвечаем на callback query сразу, чтобы избежать ошибки "query is too old"
    try:
        await call.answer()
    except Exception:
        pass  # Игнорируем ошибки, если callback уже устарел
    
    await deactivate_persona_chat(state)
    # Удаляем предыдущее сообщение с фото
    await _delete_last_photo_message(state, bot)
    profiles = list_profiles()
    data = await state.get_data()
    idx = data.get("person_index", 0)
    idx = (idx + 1) % len(profiles)
    await send_person_card(idx, call, state, bot)
    try:
        await call.message.delete()
    except Exception:
        pass

async def character_prev_callback(call: CallbackQuery, state: FSMContext, bot: Bot):
    # Отвечаем на callback query сразу, чтобы избежать ошибки "query is too old"
    try:
        await call.answer()
    except Exception:
        pass  # Игнорируем ошибки, если callback уже устарел
    
    await deactivate_persona_chat(state)
    # Удаляем предыдущее сообщение с фото
    await _delete_last_photo_message(state, bot)
    profiles = list_profiles()
    data = await state.get_data()
    idx = data.get("person_index", 0)
    idx = (idx - 1 + len(profiles)) % len(profiles)
    await send_person_card(idx, call, state, bot)
    try:
        await call.message.delete()
    except Exception:
        pass


async def character_delete_callback(call: CallbackQuery, state: FSMContext, bot: Bot):
    # Отвечаем на callback query сразу, чтобы избежать ошибки "query is too old"
    try:
        await call.answer()
    except Exception:
        pass  # Игнорируем ошибки, если callback уже устарел
    
    await deactivate_persona_chat(state)
    if not is_admin(call.from_user.id):
        await call.message.answer("Недостаточно прав для удаления.")
        return
    parts = (call.data or "").split(":", 2)
    try:
        person_index = int(parts[2]) if len(parts) > 2 else None
    except (ValueError, IndexError):
        await call.message.answer("Не удалось определить анкету.")
        return
    
    profiles = list_profiles()
    if person_index is None or person_index < 0 or person_index >= len(profiles):
        await call.message.answer("Персонаж не найден.")
        return
    
    persona_id = profiles[person_index].get("id")
    if not persona_id:
        await call.message.answer("Не удалось определить анкету.")
        return
    
    # Удаляем предыдущее сообщение с фото перед удалением персонажа
    await _delete_last_photo_message(state, bot)
    
    deleted = await delete_persona(persona_id)
    if deleted:
        await call.message.answer("✅ Анкета удалена.")
        # Кэш уже очищен в delete_persona, но на всякий случай обновляем
        invalidate_cache()
    else:
        await call.message.answer("❌ Удалить не удалось.")
    
    # Обновляем список профилей после удаления
    profiles = list_profiles(force_refresh=True)
    if not profiles:
        await call.message.answer("Нет ни одного персонажа.", reply_markup=get_reply_main_menu())
        return
    data = await state.get_data()
    idx = data.get("person_index", 0)
    if idx >= len(profiles):
        idx = 0
    await send_person_card(idx, call, state, bot)
    try:
        await call.message.delete()
    except Exception:
        pass

async def character_backmain_callback(call: CallbackQuery, state: FSMContext):
    await deactivate_persona_chat(state)
    await call.answer()


async def character_startchat_callback(call: CallbackQuery, state: FSMContext, bot: Bot):
    # Отвечаем на callback query сразу, чтобы избежать ошибки "query is too old"
    try:
        await call.answer("Запускаю чат...")
    except Exception:
        pass  # Игнорируем ошибки, если callback уже устарел
    
    # Удаляем последнее сообщение с фото перед началом чата
    await _delete_last_photo_message(state, bot)
    
    parts = (call.data or "").split(":", 2)
    try:
        person_index = int(parts[2]) if len(parts) > 2 else None
    except (ValueError, IndexError):
        await call.message.answer("Не удалось определить анкету.")
        return
    
    profiles = list_profiles()
    if person_index is None or person_index < 0 or person_index >= len(profiles):
        await call.message.answer("Персонаж не найден.")
        return
    
    persona = profiles[person_index]
    
    # Проверяем баланс токенов перед началом чата
    user_id = call.from_user.id
    
    # Проверяем безлимитный премиум (тариф 4)
    try:
        from premium.subscription import is_premium_unlimited
        if is_premium_unlimited(user_id):
            # Безлимитный премиум - можно начинать чат
            pass  # Продолжаем дальше
        else:
            # Обычная проверка баланса
            balance = get_token_balance(user_id)
            if balance <= 0:
                await call.message.answer(
                    f"❗️ Недостаточно токенов для начала чата. Баланс: {balance}.\n\n"
                    "Нажми «💰 Пополнить баланс» или используй команду /topup.",
                )
                return
    except Exception:
        # При ошибке проверяем токены как обычно
        balance = get_token_balance(user_id)
        if balance <= 0:
            await call.message.answer(
                f"❗️ Недостаточно токенов для начала чата. Баланс: {balance}.\n\n"
                "Нажми «💰 Пополнить баланс» или используй команду /topup.",
            )
            return
    
    # Увеличиваем счетчик популярности (количество запросов)
    persona_id = persona.get("id")
    if persona_id:
        increment_persona_chat_count(persona_id)
        # Очищаем кэш, чтобы обновить порядок популярности
        invalidate_cache()
    
    # Очищаем состояние wizard, если оно активно, чтобы избежать конфликтов
    data = await state.get_data()
    if data.get("wizard_draft") or data.get("wizard_editing"):
        await state.update_data(wizard_draft=None, wizard_editing=None)
    context = start_persona_chat(persona, user_id)
    intro_text = build_persona_intro(persona)
    if intro_text:
        history = context.history or []
        history.append({"role": "assistant", "content": intro_text})
        context.history = history
    await state.update_data(
        persona_chat_context=context.to_dict(),
        persona_chat_active=True,
    )
    # Форматируем intro для отображения
    persona_name = persona.get("name", "Персонаж")
    formatted_intro = format_persona_response(intro_text, persona_name)
    # Логика кэширования: сначала пробуем использовать file_id (Telegram не скачивает файл)
    # Если file_id невалиден - загружаем файл и обновляем file_id
    photo_file_id = persona.get("photo_file_id")
    photo_path = persona.get("photo")
    persona_id = persona.get("id")
    sent_message = None
    
    # Проверяем, что photo_file_id не пустой и не None
    if photo_file_id and photo_file_id.strip():
        # Пробуем использовать кэшированный file_id - Telegram НЕ будет скачивать файл
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Используем кэшированный file_id для persona_id={persona_id}: {photo_file_id[:20]}...")
        try:
            sent_message = await call.message.answer_photo(
                photo_file_id,  # Передаем file_id как строку - Telegram использует кэш
                caption=formatted_intro,
                parse_mode="HTML",
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
        if photo_path:
            try:
                import logging
                logger = logging.getLogger(__name__)
                logger.info(f"Загружаем файл для persona_id={persona_id} из {photo_path[:50]}...")
                if photo_path.startswith("http://") or photo_path.startswith("https://"):
                    photo = URLInputFile(photo_path)
                else:
                    photo = FSInputFile(photo_path)
                sent_message = await call.message.answer_photo(
                    photo,  # Telegram скачивает файл
                    caption=formatted_intro,
                    parse_mode="HTML",
                )
                # Сохраняем file_id в БД для последующих отправок
                if persona_id and sent_message.photo:
                    new_file_id = sent_message.photo[-1].file_id
                    logger.info(f"Сохраняем новый file_id для persona_id={persona_id}: {new_file_id[:20]}...")
                    update_persona(persona_id, photo_file_id=new_file_id)
                    invalidate_cache()
            except Exception:
                await call.message.answer(formatted_intro, parse_mode="HTML")
        else:
            await call.message.answer(formatted_intro, parse_mode="HTML")

def register_menu_handlers(dp: Dispatcher):
    """
    Регистрирует хэндлеры главного меню.
    """
    # Обработчики текстовых кнопок
    dp.message.register(profile_menu_handler, lambda m: m.text == "✨ Профиль")
    dp.message.register(popular_menu_handler, lambda m: m.text == "⭐ Популярные Персонажи")
    dp.message.register(back_menu_handler, lambda m: m.text == "🏡 Menu")
    
    # Обработчики inline кнопок главного меню
    dp.callback_query.register(
        profile_menu_handler, 
        lambda c: c.data == "menu:profile"
    )
    dp.callback_query.register(
        popular_menu_handler, 
        lambda c: c.data == "menu:popular"
    )
    # menu:mychars обрабатывается в register_my_char_handlers
    
    # Callback'и для анкеты популярных персонажей
    dp.callback_query.register(character_next_callback, lambda c: c.data == "character:next")
    dp.callback_query.register(character_prev_callback, lambda c: c.data == "character:prev")
    dp.callback_query.register(character_delete_callback, lambda c: c.data and c.data.startswith("character:delete:"))
    dp.callback_query.register(character_startchat_callback, lambda c: c.data and c.data.startswith("character:startchat:"))
    dp.callback_query.register(character_backmain_callback, lambda c: c.data == "character:backmain")
    
    # Регистрация обработчиков "Мои персонажи"
    register_my_char_handlers(dp)
