"""База данных профилей пользователей."""

import sqlite3
import json

DB_NAME = "guitar_users.db"


def connect():
    return sqlite3.connect(DB_NAME)


def init_db():
    with connect() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                known_chords TEXT DEFAULT '[]',
                goals TEXT DEFAULT '',
                experience TEXT DEFAULT 'Начинающий'
            )
        """)


def get_profile(user_id):
    with connect() as db:
        row = db.execute(
            "SELECT known_chords, goals, experience "
            "FROM users WHERE user_id = ?",
            (user_id,)
        ).fetchone()

    if row is None:
        return {
            "known_chords": [],
            "goals": "",
            "experience": "Начинающий",
        }

    return {
        "known_chords": json.loads(row[0]),
        "goals": row[1],
        "experience": row[2],
    }


def update_profile(user_id, known_chords=None,
                   goals=None, experience=None):
    profile = get_profile(user_id)

    if known_chords is not None:
        profile["known_chords"] = known_chords

    if goals is not None:
        profile["goals"] = goals

    if experience is not None:
        profile["experience"] = experience

    with connect() as db:
        db.execute("""
            INSERT OR REPLACE INTO users
            (user_id, known_chords, goals, experience)
            VALUES (?, ?, ?, ?)
        """, (
            user_id,
            json.dumps(profile["known_chords"]),
            profile["goals"],
            profile["experience"],
        ))


def format_profile(user_id):
    profile = get_profile(user_id)

    chords = profile["known_chords"]
    chords_text = ", ".join(chords) if chords else "Пока не указаны"

    return (
        "👤 Твой профиль гитариста\n\n"
        f"🎸 Уровень: {profile['experience']}\n"
        f"🎼 Знаю аккорды: {chords_text}\n"
        f"🎯 Мои цели: {profile['goals'] or 'Пока не указаны'}"
    )
