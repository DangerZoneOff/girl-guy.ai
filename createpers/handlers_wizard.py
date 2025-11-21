"""
Обработчики для интерактивного мастера создания персонажа.
Альтернатива FSM - все поля редактируются через inline-кнопки.
"""

import os
from aiogram import Dispatcher, Bot
from aiogram.filters import Command, BaseFilter
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from .wizard import PersonaDraft, get_wizard_keyboard, format_draft_preview
from knops.keyboards import get_reply_main_menu
from pers.database import create_persona
from pers.storage import save_photo
from knops.api_persons import invalidate_cache
from ai.chat_state import deactivate_persona_chat

PERS_DIR = os.path.join(os.path.dirname(__file__), "..", "pers")
USERS_DIR = os.path.join(PERS_DIR, "users")


class WizardEditingFilter(BaseFilter):
    """Фильтр, проверяющий активность режима редактирования в мастере"""
    
    async def __call__(self, message: Message, state: FSMContext) -> bool:
        data = await state.get_data()
        return bool(data.get("wizard_editing") and data.get("wizard_draft"))


async def start_wizard(msg: Message, state: FSMContext) -> None:
    """Начинает мастер создания персонажа"""
    await deactivate_persona_chat(state)
    
    user_id = msg.from_user.id if msg.from_user else 0
    
    # Проверяем премиум статус
    is_premium_user = False
    try:
        from premium.subscription import is_premium
        is_premium_user = is_premium(user_id)
    except Exception:
        pass
    
    if not is_premium_user:
        await msg.answer(
            "❌ <b>Создание персонажей доступно только с премиум подпиской</b>\n\n"
            "Нажми «💰 Пополнить баланс» и выбери «⭐ Купить премиум» для доступа к созданию персонажей.",
            parse_mode="HTML"
        )
        return
    
    draft = PersonaDraft(owner_id=user_id)
    
    await state.update_data(wizard_draft=draft.to_dict())
    await state.update_data(wizard_editing=None)
    
    await msg.answer(
        "🎨 <b>Мастер создания персонажа</b>\n\n"
        "Нажми на любое поле, чтобы заполнить или изменить его.\n"
        "Все поля можно редактировать в любой момент.",
        parse_mode="HTML",
        reply_markup=get_wizard_keyboard(draft)
    )


async def handle_wizard_edit(call: CallbackQuery, state: FSMContext) -> None:
    """Обрабатывает нажатие на кнопку редактирования поля"""
    await call.answer()
    
    if not call.data:
        return
    
    field = call.data.split(":")[-1]  # wizard:edit:photo -> photo
    
    data = await state.get_data()
    draft_dict = data.get("wizard_draft", {})
    draft = PersonaDraft.from_dict(draft_dict)
    
    await state.update_data(wizard_editing=field)
    
    # Получаем текущее значение поля (если есть)
    current_value = None
    if field == "photo":
        current_value = "✅ Загружено" if draft.photo_id else None
    elif field == "name":
        current_value = draft.name
    elif field == "age":
        current_value = str(draft.age) if draft.age is not None else None
    elif field == "description":
        current_value = draft.description
    elif field == "character":
        current_value = draft.character
    elif field == "scene":
        current_value = draft.scene
    elif field == "initial_scene":
        current_value = draft.initial_scene
    
    field_prompts = {
        "photo": "📷 Пришлите фото персонажа:",
        "name": "👤 Введите имя персонажа (только буквы):",
        "age": "🎂 Сколько лет персонажу? (1-100):",
        "description": "📝 Кратко опишите персонажа:",
        "character": "🎭 Опишите характер/манеру общения (обязательно, минимум 150 символов):",
        "scene": "📍 Где находится персонаж? Опишите сцену/окружение (обязательно, минимум 150 символов):",
        "initial_scene": "🎬 Опишите начальную сцену при старте диалога (что происходит, когда пользователь только начинает общение) (обязательно, минимум 150 символов):",
    }
    
    prompt = field_prompts.get(field, "Введите значение:")
    
    # Если поле уже заполнено, показываем текущее значение и предупреждение
    if current_value and field not in ["photo", "age"]:
        if field in ["character", "scene", "initial_scene"]:
            # Для длинных полей показываем первые 200 символов
            preview = current_value[:200] + "..." if len(current_value) > 200 else current_value
            prompt += f"\n\n⚠️ <b>Текущее значение будет заменено!</b>\n📄 Текущее ({len(current_value)} символов):\n<i>{preview}</i>\n\n✏️ Введите новое значение:"
        else:
            prompt += f"\n\n⚠️ <b>Текущее значение будет заменено!</b>\n📄 Текущее: <i>{current_value}</i>\n\n✏️ Введите новое значение:"
    elif current_value and field == "age":
        prompt += f"\n\n⚠️ <b>Текущее значение будет заменено!</b>\n📄 Текущее: <i>{current_value} лет</i>\n\n✏️ Введите новое значение:"
    elif current_value and field == "photo":
        prompt += "\n\n⚠️ <b>Текущее фото будет заменено!</b>\n✏️ Пришлите новое фото:"
    
    await call.message.answer(prompt, parse_mode="HTML")


async def handle_wizard_input(msg: Message, state: FSMContext) -> None:
    """Обрабатывает ввод данных для редактируемого поля"""
    data = await state.get_data()
    editing_field = data.get("wizard_editing")
    draft_dict = data.get("wizard_draft")
    
    # Проверяем, что мы в режиме редактирования и есть черновик
    if not editing_field or not draft_dict:
        return  # Не в режиме редактирования или нет активного черновика
    
    draft = PersonaDraft.from_dict(draft_dict)
    
    # Обработка фото
    if editing_field == "photo":
        if not msg.photo:
            await msg.answer("❌ Нужно фото! Пришлите изображение.")
            return
        draft.photo_id = msg.photo[-1].file_id
        await msg.answer("✅ Фото сохранено!")
    
    # Обработка имени
    elif editing_field == "name":
        name = msg.text.strip() if msg.text else ""
        if not name.replace(' ', '').isalpha():
            await msg.answer("❌ Имя должно содержать только буквы! Повторите.")
            return
        draft.name = name
        await msg.answer(f"✅ Имя сохранено: {name}")
    
    # Обработка возраста
    elif editing_field == "age":
        try:
            age = int(msg.text.strip()) if msg.text else 0
            if not (1 <= age <= 100):
                raise ValueError
            draft.age = age
            await msg.answer(f"✅ Возраст сохранен: {age} лет")
        except ValueError:
            await msg.answer("❌ Возраст должен быть числом от 1 до 100!")
            return
    
    # Обработка описания (обязательное)
    elif editing_field == "description":
        desc = msg.text.strip() if msg.text else ""
        if not desc:
            await msg.answer("❌ Описание обязательно! Введите описание персонажа.")
            return
        # Полностью заменяем старое значение новым (не добавляем!)
        draft.description = desc
        await msg.answer(f"✅ Описание сохранено! ({len(desc)} символов)\n\n💡 <i>Старое значение полностью заменено новым.</i>", parse_mode="HTML")
    
    # Обработка характера (обязательное, минимум 150 символов)
    elif editing_field == "character":
        MIN_LENGTH = 150
        character = msg.text.strip() if msg.text else ""
        if not character:
            await msg.answer(f"❌ Характер обязателен! Введите минимум {MIN_LENGTH} символов.")
            return
        if len(character) < MIN_LENGTH:
            await msg.answer(f"❌ Характер должен содержать минимум {MIN_LENGTH} символов. Сейчас: {len(character)}/{MIN_LENGTH}")
            return
        # Полностью заменяем старое значение новым (не добавляем!)
        draft.character = character
        await msg.answer(f"✅ Характер сохранен! ({len(character)} символов)\n\n💡 <i>Старое значение полностью заменено новым.</i>", parse_mode="HTML")
    
    # Обработка сцены (обязательное, минимум 150 символов)
    elif editing_field == "scene":
        MIN_LENGTH = 150
        scene = msg.text.strip() if msg.text else ""
        if not scene:
            await msg.answer(f"❌ Сцена обязательна! Введите минимум {MIN_LENGTH} символов.")
            return
        if len(scene) < MIN_LENGTH:
            await msg.answer(f"❌ Сцена должна содержать минимум {MIN_LENGTH} символов. Сейчас: {len(scene)}/{MIN_LENGTH}")
            return
        # Полностью заменяем старое значение новым (не добавляем!)
        draft.scene = scene
        await msg.answer(f"✅ Сцена сохранена! ({len(scene)} символов)\n\n💡 <i>Старое значение полностью заменено новым.</i>", parse_mode="HTML")
    
    # Обработка начальной сцены (обязательное, минимум 150 символов)
    elif editing_field == "initial_scene":
        MIN_LENGTH = 150
        initial_scene = msg.text.strip() if msg.text else ""
        if not initial_scene:
            await msg.answer(f"❌ Начальная сцена обязательна! Введите минимум {MIN_LENGTH} символов.")
            return
        if len(initial_scene) < MIN_LENGTH:
            await msg.answer(f"❌ Начальная сцена должна содержать минимум {MIN_LENGTH} символов. Сейчас: {len(initial_scene)}/{MIN_LENGTH}")
            return
        # Полностью заменяем старое значение новым (не добавляем!)
        draft.initial_scene = initial_scene
        await msg.answer(f"✅ Начальная сцена сохранена! ({len(initial_scene)} символов)\n\n💡 <i>Старое значение полностью заменено новым.</i>", parse_mode="HTML")
    
    # Сохраняем обновленный черновик
    await state.update_data(wizard_draft=draft.to_dict())
    await state.update_data(wizard_editing=None)
    
    # Показываем обновленную клавиатуру
    await msg.answer(
        "🎨 <b>Мастер создания персонажа</b>\n\n"
        "Нажми на любое поле, чтобы заполнить или изменить его.",
        parse_mode="HTML",
        reply_markup=get_wizard_keyboard(draft)
    )


async def handle_wizard_confirm(call: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Подтверждает создание персонажа"""
    await call.answer()
    
    data = await state.get_data()
    draft_dict = data.get("wizard_draft", {})
    draft = PersonaDraft.from_dict(draft_dict)
    
    if not draft.is_complete():
        missing = draft.get_missing_fields()
        await call.message.answer(
            f"❌ Заполните все обязательные поля: {', '.join(missing)}"
        )
        return
    
    # Показываем превью
    preview_text = format_draft_preview(draft)
    
    # Добавляем сообщение о создании, проверяя лимит
    creating_msg = "\n\n💾 Создаю персонажа..."
    if len(preview_text) + len(creating_msg) > 4096:
        # Если превью уже близко к лимиту, отправляем отдельным сообщением
        await call.message.answer(preview_text, parse_mode="HTML")
        await call.message.answer("💾 Создаю персонажа...")
    else:
        await call.message.answer(
            preview_text + creating_msg,
            parse_mode="HTML"
        )
    
    # Создаем персонажа
    try:
        owner_id = draft.owner_id
        
        # Скачиваем фото
        photo_path = None
        photo_url = None
        if draft.photo_id:
            photo = await bot.get_file(draft.photo_id)
            # Скачиваем во временный файл
            import tempfile
            tmp_path = None
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_file:
                    tmp_path = tmp_file.name
                    await bot.download_file(photo.file_path, tmp_path)
                
                # Читаем файл
                with open(tmp_path, "rb") as f:
                    file_data = f.read()
            finally:
                # Удаляем временный файл
                if tmp_path and os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            
            # Сохраняем фото (в Yandex Object Storage для всех персонажей, если настроено)
            # Все фото (опубликованные и неопубликованные) сохраняются в одно место
            import logging
            logger = logging.getLogger(__name__)
            
            storage_type = os.getenv("STORAGE_TYPE", "local")
            yandex_bucket = os.getenv("YANDEX_BUCKET")
            yandex_key = os.getenv("YANDEX_ACCESS_KEY_ID")
            
            # Логируем настройки для отладки
            logger.info(f"STORAGE_TYPE={storage_type}, YANDEX_BUCKET={'установлен' if yandex_bucket else 'НЕ установлен'}, YANDEX_KEY={'установлен' if yandex_key else 'НЕ установлен'}")
            
            # Явно передаем тип хранилища, чтобы все персонажи сохранялись одинаково
            photo_path, photo_url = await save_photo(
                file_data,
                owner_id,
                draft.name,
                storage_type=storage_type,  # Используем тип из переменной окружения
            )
            
            # Логируем результат
            if photo_url:
                logger.info(f"Фото сохранено в облако: {photo_url}")
            else:
                logger.warning(f"Фото сохранено локально: {photo_path}")
        
        # Создаем персонажа в БД (использует параметризованные запросы - безопасно!)
        try:
            persona_id = create_persona(
                owner_id=owner_id,
                name=draft.name,
                age=draft.age,
                description=draft.description,
                character=draft.character,
                scene=draft.scene,
                initial_scene=draft.initial_scene,
                photo_path=photo_path,
                photo_url=photo_url,
                public=False,
            )
        except Exception as db_error:
            error_str = str(db_error)
            if "UNIQUE constraint failed" in error_str or "UNIQUE constraint" in error_str:
                await call.message.answer(
                    f"❌ Персонаж с именем «{draft.name}» уже существует!\n"
                    f"У тебя уже есть персонаж с таким именем. Выбери другое имя.",
                    reply_markup=get_reply_main_menu(),
                )
                # Очищаем состояние
                await state.update_data(wizard_draft=None)
                await state.update_data(wizard_editing=None)
                return
            else:
                raise  # Пробрасываем другие ошибки дальше
        
        invalidate_cache()
        
        await call.message.answer(
            "✅ Персонаж создан! Теперь он доступен в разделе «Мои персонажи».",
            reply_markup=get_reply_main_menu(),
        )
        
        # Очищаем состояние
        await state.update_data(wizard_draft=None)
        await state.update_data(wizard_editing=None)
        
    except Exception as e:
        await call.message.answer(
            f"❌ Ошибка при создании персонажа: {str(e)}",
            reply_markup=get_reply_main_menu(),
        )


async def handle_wizard_cancel(call: CallbackQuery, state: FSMContext) -> None:
    """Отменяет создание персонажа"""
    await call.answer("Создание отменено")
    await state.update_data(wizard_draft=None)
    await state.update_data(wizard_editing=None)
    await call.message.answer(
        "❌ Создание персонажа отменено.",
        reply_markup=get_reply_main_menu()
    )


async def handle_wizard_help(call: CallbackQuery, state: FSMContext) -> None:
    """Показывает подсказку о незаполненных полях"""
    data = await state.get_data()
    draft_dict = data.get("wizard_draft", {})
    draft = PersonaDraft.from_dict(draft_dict)
    missing = draft.get_missing_fields()
    await call.answer(
        f"Заполните: {', '.join(missing)}",
        show_alert=True
    )


def register_wizard_handlers(dp: Dispatcher) -> None:
    """Регистрирует обработчики мастера создания персонажа"""
    # Команда и кнопка запуска
    dp.message.register(start_wizard, Command("createpersona"))
    dp.message.register(start_wizard, lambda m: m.text == '✨ Создать персонажа')
    
    # Редактирование полей через callback
    dp.callback_query.register(
        handle_wizard_edit,
        lambda c: c.data and c.data.startswith("wizard:edit:")
    )
    
    # Ввод данных (обрабатывается только если есть wizard_editing в state)
    dp.message.register(handle_wizard_input, WizardEditingFilter())
    
    # Подтверждение и отмена
    dp.callback_query.register(handle_wizard_confirm, lambda c: c.data == "wizard:confirm")
    dp.callback_query.register(handle_wizard_cancel, lambda c: c.data == "wizard:cancel")
    dp.callback_query.register(handle_wizard_help, lambda c: c.data == "wizard:help")

