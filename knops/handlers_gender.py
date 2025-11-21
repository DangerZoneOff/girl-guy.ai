"""
Обработчики событий, связанных с выбором пола пользователем.
Здесь только логика реакций на нажатия кнопок (gender) и команда /start.
"""
from aiogram import Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from .keyboards import get_gender_keyboard, get_main_menu_keyboard, get_reply_main_menu
from .user_profiles import set_registration_date
from ai.chat_state import deactivate_persona_chat
from refferals import process_referral_payload

async def start_command(message: Message, state: FSMContext):
    """
    Старт: если пользователь уже выбрал пол — главное меню, иначе показать выбор пола.
    """
    await deactivate_persona_chat(state)
    # Обрабатываем реферальный payload (если он был)
    if message.from_user:
        payload = None
        if message.text:
            parts = message.text.strip().split(maxsplit=1)
            if len(parts) > 1:
                payload = parts[1].strip()
        referral_message = process_referral_payload(message.from_user.id, payload)
        if referral_message:
            await message.answer(referral_message, parse_mode="HTML")
    data = await state.get_data()
    if data.get("gender"):
        await message.answer("Главное меню", reply_markup=get_reply_main_menu())
    else:
        text = (
            "👋 Добро пожаловать в Girl-Guy!\n\n"
            "Выбери свой пол, чтобы начать общение:"
        )
        await message.answer(text, reply_markup=get_gender_keyboard())

async def handle_gender_callback(callback: CallbackQuery, state: FSMContext):
    """
    После выбора пола — сохраняет дату регистрации пользователя в json, выводит главное меню (без кнопки "Назад").
    """
    await callback.answer()
    data = callback.data
    user = callback.from_user
    if data and data.startswith("gender:") and user:
        await deactivate_persona_chat(state)
        gender = data.split(":")[1]
        await state.update_data(gender=gender)
        set_registration_date(user.id)
        await callback.message.answer(
            "Пол успешно выбран! Теперь доступен весь функционал бота.\n\nГлавное меню:",
            reply_markup=get_reply_main_menu()
        )

def register_gender_handlers(dp: Dispatcher):
    """
    Регистрирует все обработчики, относящиеся к выбору пола.
    (должно быть вызвано внутри main.py)
    """
    dp.message.register(start_command, Command("start"))
    dp.callback_query.register(handle_gender_callback, lambda c: c.data and c.data.startswith("gender:"))
