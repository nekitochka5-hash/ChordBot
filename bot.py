
"""Главный файл Telegram-бота AI Гитара."""

import asyncio
import logging
import os
import re
import tempfile

from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

import chords
import keyboards
import chord_shapes
import guitar_tools
import database
import ai_guitarist
import profile_tools


logging.basicConfig(
    format="%(asctime)s %(levelname)s %(message)s",
    level=logging.INFO,
)

log = logging.getLogger("ai_guitar")

MAX_BYTES = 20 * 1024 * 1024

AUDIO_EXT = (
    ".mp3", ".wav", ".flac", ".m4a", ".ogg",
    ".opus", ".aac", ".wma", ".mp4"
)

ANALYSIS_LIMIT = asyncio.Semaphore(1)

WELCOME = (
    "Привет! Я AI Гитара 🎸\n\n"
    "Я помогу разбирать песни, учиться играть "
    "и работать с аккордами.\n\n"
    "Выбирай нужный раздел в меню!"
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        WELCOME,
        reply_markup=keyboards.main_menu(),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "🎸 AI Гитара — музыкальный помощник.\n\n"
        "🎵 Подбор аккордов — отправь аудиофайл.\n"
        "🤖 AI Гитарист — вопросы о музыке.\n"
        "🎸 Инструменты — работа с аккордами.\n"
        "👤 Мой профиль — твой прогресс.\n\n"
        "Команды:\n"
        "/addchord Am — добавить аккорд\n"
        "/goal текст — записать цель\n"
        "/level текст — изменить уровень.",
        reply_markup=keyboards.main_menu(),
    )


async def show_profile(update, context):
    user_id = update.effective_user.id
    await update.effective_message.reply_text(
        database.format_profile(user_id),
        reply_markup=keyboards.main_menu(),
    )


async def add_chord_command(update, context):
    if not context.args:
        await update.message.reply_text("Пример: /addchord Am")
        return

    chord = context.args[0].strip()
    profile_tools.add_chord(update.effective_user.id, chord)

    await update.message.reply_text(
        f"🎸 Аккорд {chord} добавлен в профиль!"
    )


async def goal_command(update, context):
    if not context.args:
        await update.message.reply_text("Напиши цель после /goal")
        return

    profile_tools.set_goals(
        update.effective_user.id,
        " ".join(context.args),
    )
    await update.message.reply_text("🎯 Цель сохранена!")


async def level_command(update, context):
    if not context.args:
        await update.message.reply_text("Напиши уровень после /level")
        return

    profile_tools.set_experience(
        update.effective_user.id,
        " ".join(context.args),
    )
    await update.message.reply_text("🎸 Уровень обновлён!")


async def handle_audio(update, context):
    msg = update.effective_message
    media = msg.audio or msg.document

    if media is None:
        return

    if msg.document:
        name = (msg.document.file_name or "").lower()
        mime = msg.document.mime_type or ""

        if not (
            name.endswith(AUDIO_EXT)
            or mime.startswith("audio/")
        ):
            await msg.reply_text(
                "Это не похоже на аудиофайл. "
                "Пришли MP3, WAV, FLAC или другой аудиоформат."
            )
            return

    if media.file_size and media.file_size > MAX_BYTES:
        await msg.reply_text("Файл больше 20 МБ. Отправь файл поменьше.")
        return

    status = await msg.reply_text("🎧 Анализирую аудио...")

    try:
        await context.bot.send_chat_action(
            msg.chat_id,
            ChatAction.TYPING,
        )

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "input")

            tg_file = await media.get_file()
            await tg_file.download_to_drive(path)

            async with ANALYSIS_LIMIT:
                result = await asyncio.to_thread(chords.analyze, path)

        parts = chords.format_result(result)
        main_chords = result.get("main_chords", [])

        context.user_data["last_chords"] = list(main_chords)

        for part in parts:
            await msg.reply_text(
                part,
                parse_mode=ParseMode.HTML,
            )

        if main_chords:
            await msg.reply_text(
                "Что хочешь сделать с найденными аккордами?",
                reply_markup=keyboards.chord_actions(),
            )

        await status.delete()

    except (ValueError, RuntimeError) as error:
        await status.edit_text(f"Не получилось обработать файл: {error}")

    except Exception:
        log.exception("Ошибка при анализе аудио")
        await status.edit_text(
            "Произошла ошибка при анализе. Попробуй другой аудиофайл."
        )


async def handle_callbacks(update, context):
    query = update.callback_query
    await query.answer()

    data = query.data or ""
    chords_list = context.user_data.get("last_chords", [])

    if not chords_list:
        await query.message.reply_text(
            "Сначала отправь песню, чтобы получить аккорды."
        )
        return

    if data.startswith("transpose_"):
        parts = data.split("_")

        if len(parts) != 3 or parts[1] not in ("up", "down"):
            return

        try:
            amount = int(parts[2])
        except ValueError:
            return

        if amount not in (1, 2):
            return

        semitones = amount if parts[1] == "up" else -amount

        answer = guitar_tools.format_transposed_chords(
            chords_list,
            semitones,
        )
        await query.message.reply_text(answer)

    elif data == "simplify_chords":
        for chord in dict.fromkeys(chords_list):
            await query.message.reply_text(
                guitar_tools.format_simplified_chord(chord)
            )


async def handle_text(update, context):
    message = update.effective_message.text.strip()

    if message == "🎵 Подобрать аккорды":
        context.user_data["awaiting_ai"] = False
        context.user_data["awaiting_shape"] = False
        await update.message.reply_text(
            "🎵 Отправь аудиофайл с песней."
        )

    elif message == "🤖 AI Гитарист":
        context.user_data["awaiting_ai"] = True
        context.user_data["awaiting_shape"] = False
        await update.message.reply_text(
            "🤖 AI Гитарист на связи!\n\n"
            "Задай вопрос о гитаре, аккордах, "
            "музыкальной теории или написании песен."
        )

    elif message == "🎸 Инструменты":
        context.user_data["awaiting_ai"] = False
        context.user_data["awaiting_shape"] = False
        await update.message.reply_text(
            "🎸 Выбери инструмент:",
            reply_markup=keyboards.tools_menu(),
        )

    elif message == "👤 Мой профиль":
        await show_profile(update, context)

    elif message == "ℹ️ Помощь":
        await help_command(update, context)

    elif message == "🔄 Транспонировать аккорды":
        if not context.user_data.get("last_chords"):
            await update.message.reply_text(
                "Сначала отправь песню и получи аккорды."
            )
        else:
            await update.message.reply_text(
                "Выбери, насколько изменить тональность:",
                reply_markup=keyboards.chord_actions(),
            )

    elif message == "🎼 Упростить аккорды":
        chords_list = context.user_data.get("last_chords", [])

        if not chords_list:
            await update.message.reply_text(
                "Сначала отправь песню и получи аккорды."
            )
        else:
            for chord in dict.fromkeys(chords_list):
                await update.message.reply_text(
                    guitar_tools.format_simplified_chord(chord)
                )

    elif message == "🎸 Схемы аккордов":
        context.user_data["awaiting_shape"] = True
        context.user_data["awaiting_ai"] = False
        await update.message.reply_text(
            "Напиши название аккорда, например Am, C, G или F."
        )

    elif message == "⬅️ Главное меню":
        context.user_data["awaiting_ai"] = False
        context.user_data["awaiting_shape"] = False
        await update.message.reply_text(
            "Главное меню 🎸",
            reply_markup=keyboards.main_menu(),
        )

    elif context.user_data.get("awaiting_shape"):
        chord = message.strip()
        await update.message.reply_text(
            chord_shapes.format_chord_shape(chord)
        )
        context.user_data["awaiting_shape"] = False

    elif context.user_data.get("awaiting_ai"):
        answer = ai_guitarist.get_response(message)
        await update.message.reply_text(answer)

    else:
        await update.message.reply_text(
            "Выбери раздел в меню или нажми «Помощь»."
        )


def main():
    token = os.environ.get("BOT_TOKEN")

    if not token:
        raise SystemExit(
            "Не задан BOT_TOKEN. Проверь переменные Railway."
        )

    database.init_db()

    app = (
        Application.builder()
        .token(token)
        .read_timeout(120)
        .write_timeout(120)
        .connect_timeout(30)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("addchord", add_chord_command))
    app.add_handler(CommandHandler("goal", goal_command))
    app.add_handler(CommandHandler("level", level_command))

    app.add_handler(CallbackQueryHandler(handle_callbacks))

    app.add_handler(
        MessageHandler(
            filters.AUDIO | filters.Document.ALL,
            handle_audio,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_text,
        )
    )

    log.info("AI Гитара запущен")
    app.run_polling()


if __name__ == "__main__":
    main()
