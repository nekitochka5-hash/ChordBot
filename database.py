
"""База данных профилей пользователей."""

import json
import os
import sqlite3


# По умолчанию база хранится рядом с программой.
# Для постоянного хранилища Railway позже укажем DATABASE_PATH.
DB_NAME = os.environ.get("DATABASE_PATH", "guitar_users.db")


def connect():
    """Создаёт подключение к базе данных."""
    folder = os.path.dirname(DB_NAME)

    if folder:
        os.makedirs(folder, exist_ok=True)

    return sqlite3.connect(DB_NAME, timeout=30)


def init_db():
    """Создаёт таблицу пользователей, если её ещё нет."""
    with connect() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                known_chords TEXT NOT NULL DEFAULT '[]',
                goals TEXT NOT NULL DEFAULT '',
                experience TEXT NOT NULL DEFAULT 'Начинающий'
            )
        """)


def get_profile(user_id):
    """Получает профиль пользователя."""
    with connect() as db:
        row = db.execute(
            """
            SELECT known_chords, goals, experience
            FROM users
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

    if row is None:
        return {
            "known_chords": [],
            "goals": "",
            "experience": "Начинающий",
        }

    try:
        known_chords = json.loads(row[0])
    except (TypeError, json.JSONDecodeError):
        known_chords = []

    return {
        "known_chords": known_chords,
        "goals": row[1] or "",
        "experience": row[2] or "Начинающий",
    }


def update_profile(
    user_id,
    known_chords=None,
    goals=None,
    experience=None,
):
    """Обновляет данные профиля."""
    profile = get_profile(user_id)

    if known_chords is not None:
        profile["known_chords"] = known_chords

    if goals is not None:
        profile["goals"] = goals

    if experience is not None:
        profile["experience"] = experience

    with connect() as db:
        db.execute(
            """
            INSERT INTO users (
                user_id,
                known_chords,
                goals,
                experience
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                known_chords = excluded.known_chords,
                goals = excluded.goals,
                experience = excluded.experience
            """,
            (
                user_id,
                json.dumps(
                    profile["known_chords"],
                    ensure_ascii=False,
                ),
                profile["goals"],
                profile["experience"],
            ),
        )


def format_profile(user_id):
    """Формирует текст профиля для Telegram."""
    profile = get_profile(user_id)

    chords = profile["known_chords"]
    chords_text = (
        ", ".join(chords)
        if chords
        else "Пока не указаны"
    )

    return (
        "👤 Твой профиль гитариста\n\n"
        f"🎸 Уровень: {profile['experience']}\n"
        f"🎼 Знаю аккорды: {chords_text}\n"
        f"🎯 Мои цели: {profile['goals'] or 'Пока не указаны'}"
    )
