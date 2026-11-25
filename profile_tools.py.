
"""Инструменты для управления профилем гитариста."""

import database


def add_chord(user_id, chord):
    """Добавляет знакомый аккорд в профиль."""
    chord = chord.strip()

    if not chord:
        return []

    profile = database.get_profile(user_id)
    chords = profile["known_chords"]

    if chord not in chords:
        chords.append(chord)

    database.update_profile(
        user_id,
        known_chords=chords,
    )

    return chords


def remove_chord(user_id, chord):
    """Удаляет аккорд из профиля."""
    profile = database.get_profile(user_id)
    chords = profile["known_chords"]

    if chord in chords:
        chords.remove(chord)

    database.update_profile(
        user_id,
        known_chords=chords,
    )

    return chords


def set_goals(user_id, goals):
    """Сохраняет цель пользователя."""
    database.update_profile(
        user_id,
        goals=goals.strip(),
    )


def set_experience(user_id, experience):
    """Сохраняет уровень пользователя."""
    database.update_profile(
        user_id,
        experience=experience.strip(),
    )
