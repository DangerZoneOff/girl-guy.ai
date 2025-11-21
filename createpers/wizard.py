"""
Интерактивный мастер создания персонажа с возможностью редактирования полей.
Альтернатива линейному FSM - все поля видны сразу, можно редактировать любое.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram import Bot


@dataclass
class PersonaDraft:
    """Черновик персонажа"""
    owner_id: int
    photo_id: Optional[str] = None
    name: Optional[str] = None
    age: Optional[int] = None
    description: Optional[str] = None
    character: Optional[str] = None
    scene: Optional[str] = None
    initial_scene: Optional[str] = None
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> PersonaDraft:
        return cls(**data)
    
    def is_complete(self) -> bool:
        """Проверяет, заполнены ли все обязательные поля"""
        MIN_LENGTH = 150
        return all([
            self.photo_id,
            self.name,
            self.age is not None,
            self.description,  # Описание теперь обязательное
            self.character and len(self.character) >= MIN_LENGTH,
            self.scene and len(self.scene) >= MIN_LENGTH,
            self.initial_scene and len(self.initial_scene) >= MIN_LENGTH,
        ])
    
    def get_missing_fields(self) -> list[str]:
        """Возвращает список незаполненных полей"""
        MIN_LENGTH = 150
        missing = []
        if not self.photo_id:
            missing.append("Фото")
        if not self.name:
            missing.append("Имя")
        if self.age is None:
            missing.append("Возраст")
        if not self.description:
            missing.append("Описание")
        if not self.character or len(self.character) < MIN_LENGTH:
            missing.append(f"Характер (минимум {MIN_LENGTH} символов)")
        if not self.scene or len(self.scene) < MIN_LENGTH:
            missing.append(f"Сцена (минимум {MIN_LENGTH} символов)")
        if not self.initial_scene or len(self.initial_scene) < MIN_LENGTH:
            missing.append(f"Начальная сцена (минимум {MIN_LENGTH} символов)")
        return missing


def get_wizard_keyboard(draft: PersonaDraft, editing_field: Optional[str] = None) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для мастера создания персонажа.
    Показывает все поля и позволяет редактировать любое.
    """
    rows = []
    
    # Фото
    photo_status = "✅" if draft.photo_id else "❌"
    rows.append([
        InlineKeyboardButton(
            text=f"{photo_status} Фото",
            callback_data="wizard:edit:photo"
        )
    ])
    
    # Имя
    name_text = draft.name[:20] + "..." if draft.name and len(draft.name) > 20 else (draft.name or "Не указано")
    name_status = "✅" if draft.name else "❌"
    rows.append([
        InlineKeyboardButton(
            text=f"{name_status} Имя: {name_text}",
            callback_data="wizard:edit:name"
        )
    ])
    
    # Возраст
    age_text = str(draft.age) if draft.age is not None else "Не указан"
    age_status = "✅" if draft.age is not None else "❌"
    rows.append([
        InlineKeyboardButton(
            text=f"{age_status} Возраст: {age_text}",
            callback_data="wizard:edit:age"
        )
    ])
    
    # Описание (обязательное)
    desc_text = draft.description[:20] + "..." if draft.description and len(draft.description) > 20 else (draft.description or "Не указано")
    desc_status = "✅" if draft.description else "❌"
    rows.append([
        InlineKeyboardButton(
            text=f"{desc_status} Описание: {desc_text}",
            callback_data="wizard:edit:description"
        )
    ])
    
    # Характер (обязательное, минимум 150 символов)
    MIN_LENGTH = 150
    char_text = draft.character[:20] + "..." if draft.character and len(draft.character) > 20 else (draft.character or "Не указан")
    if draft.character and len(draft.character) >= MIN_LENGTH:
        char_status = "✅"
    elif draft.character:
        char_status = f"⚠️ ({len(draft.character)}/{MIN_LENGTH})"
    else:
        char_status = "❌"
    rows.append([
        InlineKeyboardButton(
            text=f"{char_status} Характер: {char_text}",
            callback_data="wizard:edit:character"
        )
    ])
    
    # Сцена (обязательное, минимум 150 символов)
    scene_text = draft.scene[:20] + "..." if draft.scene and len(draft.scene) > 20 else (draft.scene or "Не указана")
    if draft.scene and len(draft.scene) >= MIN_LENGTH:
        scene_status = "✅"
    elif draft.scene:
        scene_status = f"⚠️ ({len(draft.scene)}/{MIN_LENGTH})"
    else:
        scene_status = "❌"
    rows.append([
        InlineKeyboardButton(
            text=f"{scene_status} Сцена: {scene_text}",
            callback_data="wizard:edit:scene"
        )
    ])
    
    # Начальная сцена (обязательное, минимум 150 символов)
    initial_scene_text = draft.initial_scene[:20] + "..." if draft.initial_scene and len(draft.initial_scene) > 20 else (draft.initial_scene or "Не указана")
    if draft.initial_scene and len(draft.initial_scene) >= MIN_LENGTH:
        initial_scene_status = "✅"
    elif draft.initial_scene:
        initial_scene_status = f"⚠️ ({len(draft.initial_scene)}/{MIN_LENGTH})"
    else:
        initial_scene_status = "❌"
    rows.append([
        InlineKeyboardButton(
            text=f"{initial_scene_status} Начальная сцена: {initial_scene_text}",
            callback_data="wizard:edit:initial_scene"
        )
    ])
    
    # Разделитель
    rows.append([])
    
    # Кнопки действий
    action_row = []
    if draft.is_complete():
        action_row.append(
            InlineKeyboardButton(
                text="✅ Создать персонажа",
                callback_data="wizard:confirm"
            )
        )
    else:
        missing = draft.get_missing_fields()
        action_row.append(
            InlineKeyboardButton(
                text=f"⚠️ Заполните: {', '.join(missing[:2])}",
                callback_data="wizard:help"
            )
        )
    
    rows.append(action_row)
    
    rows.append([
        InlineKeyboardButton(text="❌ Отмена", callback_data="wizard:cancel")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _truncate_text(text: str, max_length: int) -> str:
    """Обрезает текст до максимальной длины, сохраняя HTML-теги."""
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
    
    return truncated + "..."


def format_draft_preview(draft: PersonaDraft) -> str:
    """Форматирует превью черновика для подтверждения"""
    MIN_LENGTH = 150
    TELEGRAM_MAX_LENGTH = 4096  # Лимит Telegram для сообщений
    MAX_FIELD_PREVIEW = 500  # Максимальная длина поля в превью
    
    lines = ["📋 <b>Превью персонажа:</b>\n"]
    
    if draft.photo_id:
        lines.append("📷 Фото: ✅ Загружено")
    else:
        lines.append("📷 Фото: ❌ Не загружено")
    
    lines.append(f"👤 Имя: {draft.name or '❌ Не указано'}")
    lines.append(f"🎂 Возраст: {draft.age or '❌ Не указан'}")
    
    # Описание с обрезкой и счетчиком символов
    description = draft.description or '❌ Не указано'
    if draft.description:
        desc_len = len(draft.description)
        if desc_len > MAX_FIELD_PREVIEW:
            description = _truncate_text(draft.description, MAX_FIELD_PREVIEW)
            lines.append(f"📝 Описание ({desc_len} символов): {description}")
        else:
            lines.append(f"📝 Описание ({desc_len} символов): {description}")
    else:
        lines.append(f"📝 Описание: {description}")
    
    # Характер с обрезкой и счетчиком символов
    if draft.character and len(draft.character) >= MIN_LENGTH:
        char_len = len(draft.character)
        char_text = draft.character
        if char_len > MAX_FIELD_PREVIEW:
            char_text = _truncate_text(draft.character, MAX_FIELD_PREVIEW)
        lines.append(f"🎭 Характер ({char_len}/{MIN_LENGTH} символов): {char_text}")
    elif draft.character:
        char_len = len(draft.character)
        lines.append(f"🎭 Характер: ⚠️ {draft.character[:MAX_FIELD_PREVIEW]}... (только {char_len}/{MIN_LENGTH} символов)")
    else:
        lines.append(f"🎭 Характер: ❌ Не указан (минимум {MIN_LENGTH} символов)")
    
    # Сцена с обрезкой и счетчиком символов
    if draft.scene and len(draft.scene) >= MIN_LENGTH:
        scene_len = len(draft.scene)
        scene_text = draft.scene
        if scene_len > MAX_FIELD_PREVIEW:
            scene_text = _truncate_text(draft.scene, MAX_FIELD_PREVIEW)
        lines.append(f"📍 Сцена ({scene_len}/{MIN_LENGTH} символов): {scene_text}")
    elif draft.scene:
        scene_len = len(draft.scene)
        lines.append(f"📍 Сцена: ⚠️ {draft.scene[:MAX_FIELD_PREVIEW]}... (только {scene_len}/{MIN_LENGTH} символов)")
    else:
        lines.append(f"📍 Сцена: ❌ Не указана (минимум {MIN_LENGTH} символов)")
    
    # Начальная сцена с обрезкой и счетчиком символов
    if draft.initial_scene and len(draft.initial_scene) >= MIN_LENGTH:
        initial_len = len(draft.initial_scene)
        initial_text = draft.initial_scene
        if initial_len > MAX_FIELD_PREVIEW:
            initial_text = _truncate_text(draft.initial_scene, MAX_FIELD_PREVIEW)
        lines.append(f"🎬 Начальная сцена ({initial_len}/{MIN_LENGTH} символов): {initial_text}")
    elif draft.initial_scene:
        initial_len = len(draft.initial_scene)
        lines.append(f"🎬 Начальная сцена: ⚠️ {draft.initial_scene[:MAX_FIELD_PREVIEW]}... (только {initial_len}/{MIN_LENGTH} символов)")
    else:
        lines.append(f"🎬 Начальная сцена: ❌ Не указана (минимум {MIN_LENGTH} символов)")
    
    preview_text = "\n".join(lines)
    
    # Обрезаем весь текст, если он превышает лимит Telegram
    total_length = len(preview_text)
    if total_length > TELEGRAM_MAX_LENGTH:
        preview_text = _truncate_text(preview_text, TELEGRAM_MAX_LENGTH - 50)
        preview_text += f"\n\n⚠️ <i>Превью обрезано (было {total_length} символов, лимит Telegram: {TELEGRAM_MAX_LENGTH})</i>"
    
    # Добавляем общий счетчик символов
    preview_text += f"\n\n📊 <b>Общая длина превью: {len(preview_text)}/{TELEGRAM_MAX_LENGTH} символов</b>"
    
    return preview_text

