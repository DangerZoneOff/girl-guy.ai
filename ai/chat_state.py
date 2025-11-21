"""
Утилиты для управления состоянием чата с персонажем.
"""

from __future__ import annotations

from aiogram.fsm.context import FSMContext


async def deactivate_persona_chat(state: FSMContext) -> bool:
    """
    Выключает активный чат, возвращает True если что-то было изменено.
    """
    data = await state.get_data()
    if not data.get("persona_chat_active"):
        return False
    await state.update_data(
        persona_chat_active=False,
        persona_chat_context=None,
    )
    return True

