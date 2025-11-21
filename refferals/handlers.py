"""
Обработчики интерфейса для реферальной программы.
"""

from __future__ import annotations

from aiogram import Dispatcher
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from urllib.parse import quote_plus

from .constants import REFERRAL_BUTTON_TEXT, REFERRAL_REWARD_TOKENS
from .service import get_referral_link, get_referral_stats


def _build_referral_text(user_id: int) -> tuple[str, str, dict]:
    link = get_referral_link(user_id)
    stats = get_referral_stats(user_id)
    text = (
        "🎁 <b>Реферальная программа</b>\n\n"
        f"Приглашай друзей и получай <b>{REFERRAL_REWARD_TOKENS} токенов</b> "
        "за каждого нового пользователя.\n\n"
        f"🔗 Твоя ссылка:\n<code>{link}</code>\n\n"
        f"👥 Приглашено: {stats['invited']}\n"
        f"💰 Начислено: {stats['earned_tokens']} токенов"
    )
    return link, text, stats


def _build_share_markup(link: str) -> InlineKeyboardMarkup | None:
    if not link.startswith("http"):
        return None
    share_url = f"https://t.me/share/url?url={quote_plus(link)}"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📨 Отправить другу",
                    url=share_url,
                )
            ]
        ]
    )


async def show_referral_info(message: Message):
    if not message.from_user:
        return
    link, text, _ = _build_referral_text(message.from_user.id)
    markup = _build_share_markup(link)
    await message.answer(text, reply_markup=markup, parse_mode="HTML")


async def referral_callback(call: CallbackQuery):
    if not call.from_user:
        await call.answer()
        return
    await call.answer()
    link, text, _ = _build_referral_text(call.from_user.id)
    markup = _build_share_markup(link)
    await call.message.answer(text, reply_markup=markup, parse_mode="HTML")


def register_referral_handlers(dp: Dispatcher) -> None:
    dp.message.register(show_referral_info, lambda m: m.text == REFERRAL_BUTTON_TEXT)
    dp.message.register(show_referral_info, Command("ref"))
    dp.callback_query.register(referral_callback, lambda c: c.data == "menu:referrals")

