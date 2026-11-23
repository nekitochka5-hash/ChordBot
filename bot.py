"""Telegram-бот: присылаете песню, получаете аккорды."""
import asyncio
import logging
import os
import tempfile

from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

import chords

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)
log = logging.getLogger("chordbot")

MAX_BYTES = 20 * 1024 * 1024  # Telegram не даёт ботам скачивать файлы больше 20 МБ
AUDIO_EXT = (".mp3", ".wav", ".flac", ".m4a", ".ogg", ".opus", ".aac", ".wma", ".mp4")
ANALYSIS_LIMIT = asyncio.Semaphore(1)  # анализ тяжёлый: обрабатываем по одной песне

WELCOME = (
    "Привет! Я слушаю песни и подбираю аккорды 🎸\n\n"
    "Пришлите мне аудиофайл (mp3, wav, m4a, ogg) — до 20 МБ. "
    "Я отвечу тональностью, основными аккордами и аккордами по времени.\n\n"
    "Лучше всего получается на песнях с чётким звуком гитары, пианино или группы."
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME)


async def text_hint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Пришлите аудиофайл с песней, и я подберу аккорды.")


async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    media = msg.audio or msg.voice or msg.document
    if media is None:
        return
    if msg.document:
        name = (msg.document.file_name or "").lower()
        mime = msg.document.mime_type or ""
        if not (name.endswith(AUDIO_EXT) or mime.startswith("audio/")):
            await msg.reply_text("Это не похоже на аудио. Пришлите mp3, wav, m4a или ogg.")
            return
    if media.file_size and media.file_size > MAX_BYTES:
        await msg.reply_text("Файл больше 20 МБ — Telegram не разрешает мне его скачать. "
                             "Сожмите в mp3 и пришлите ещё раз.")
        return

    status = await msg.reply_text("Слушаю… обычно это занимает от 20 секунд до минуты ⏳")
    await context.bot.send_chat_action(msg.chat_id, ChatAction.TYPING)

    try:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "input")
            tg_file = await media.get_file()
            await tg_file.download_to_drive(path)
            async with ANALYSIS_LIMIT:
                result = await asyncio.to_thread(chords.analyze, path)
        parts = chords.format_result(result)
    except ValueError as e:
        await status.edit_text(f"Не получилось: {e}")
        return
    except Exception:
        log.exception("Ошибка при анализе")
        await status.edit_text("Что-то пошло не так на моей стороне. Попробуйте другой файл.")
        return

    for part in parts:
        await msg.reply_text(part, parse_mode=ParseMode.HTML)
    await status.delete()


def main():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise SystemExit("Не задан BOT_TOKEN. Укажите токен от @BotFather (см. README.md).")
    app = (
        Application.builder()
        .token(token)
        .concurrent_updates(True)
        .read_timeout(120)
        .write_timeout(120)
        .connect_timeout(30)
        .build()
    )
    app.add_handler(CommandHandler(["start", "help"], start))
    app.add_handler(MessageHandler(filters.AUDIO | filters.VOICE | filters.Document.ALL, handle_audio))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_hint))
    log.info("Бот запущен")
    app.run_polling()


if __name__ == "__main__":
    main()
