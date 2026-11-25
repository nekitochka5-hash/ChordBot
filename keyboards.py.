
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
)


def main_menu():
    """Главное меню бота."""
    keyboard = [
        [
            KeyboardButton("🎵 Подобрать аккорды"),
            KeyboardButton("🤖 AI Гитарист"),
        ],
        [
            KeyboardButton("🎸 Инструменты"),
            KeyboardButton("👤 Мой профиль"),
        ],
        [
            KeyboardButton("ℹ️ Помощь"),
        ],
    ]

    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        is_persistent=True,
    )


def tools_menu():
    """Меню музыкальных инструментов."""
    keyboard = [
        [KeyboardButton("🔄 Транспонировать аккорды")],
        [KeyboardButton("🎼 Упростить аккорды")],
        [KeyboardButton("🎸 Схемы аккордов")],
        [KeyboardButton("⬅️ Главное меню")],
    ]

    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
    )


def chord_actions():
    """Кнопки для управления найденными аккордами."""
    keyboard = [
        [
            InlineKeyboardButton(
                "⬆️ На полтона",
                callback_data="transpose_up_1",
            ),
            InlineKeyboardButton(
                "⬇️ На полтона",
                callback_data="transpose_down_1",
            ),
        ],
        [
            InlineKeyboardButton(
                "⬆️ На тон",
                callback_data="transpose_up_2",
            ),
            InlineKeyboardButton(
                "⬇️ На тон",
                callback_data="transpose_down_2",
            ),
        ],
        [
            InlineKeyboardButton(
                "🎼 Упростить",
                callback_data="simplify_chords",
            ),
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


def back_to_menu():
    """Кнопка возврата в главное меню."""
    keyboard = [
        [KeyboardButton("⬅️ Главное меню")],
    ]

    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
    )
