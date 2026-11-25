
"""Инструменты для работы с гитарными аккордами."""

from chord_shapes import EASY_SHAPES, CHORD_SHAPES


NOTES = [
    "C", "C#", "D", "D#", "E", "F",
    "F#", "G", "G#", "A", "A#", "B"
]

# Альтернативные названия нот
NOTE_ALIASES = {
    "Db": "C#",
    "Eb": "D#",
    "Gb": "F#",
    "Ab": "G#",
    "Bb": "A#",
}


def normalize_chord(chord):
    """Приводит название аккорда к единому виду."""
    is_minor = chord.endswith("m")
    root = chord[:-1] if is_minor else chord
    root = NOTE_ALIASES.get(root, root)

    return root + ("m" if is_minor else "")


def transpose_chord(chord, semitones):
    """Транспонирует один мажорный или минорный аккорд."""
    chord = normalize_chord(chord)

    is_minor = chord.endswith("m")
    root = chord[:-1] if is_minor else chord

    if root not in NOTES:
        return chord

    index = NOTES.index(root)
    new_index = (index + semitones) % 12

    new_chord = NOTES[new_index]

    if is_minor:
        new_chord += "m"

    return new_chord


def transpose_chords(chords, semitones):
    """Транспонирует список аккордов."""
    return [
        transpose_chord(chord, semitones)
        for chord in chords
    ]


def simplify_chord(chord):
    """Ищет доступную аппликатуру аккорда."""
    chord = normalize_chord(chord)

    if chord in EASY_SHAPES:
        return {
            "chord": chord,
            "shape": EASY_SHAPES[chord],
            "simplified": True,
        }

    if chord in CHORD_SHAPES:
        return {
            "chord": chord,
            "shape": CHORD_SHAPES[chord],
            "simplified": False,
        }

    return None


def format_transposed_chords(chords, semitones):
    """Форматирует результат транспонирования."""
    new_chords = transpose_chords(chords, semitones)

    direction = "выше" if semitones > 0 else "ниже"

    return (
        f"🎸 Аккорды на {abs(semitones)} полутон(а) {direction}:\n\n"
        + " — ".join(new_chords)
    )


def format_simplified_chord(chord):
    """Показывает аппликатуру аккорда."""
    result = simplify_chord(chord)

    if result is None:
        return f"Для аккорда {chord} пока нет схемы."

    if result["simplified"]:
        title = "Упрощённая аппликатура"
    else:
        title = "Другой вариант пока не найден"

    strings = " ".join(result["shape"])

    return (
        f"🎸 Аккорд: {result['chord']}\n"
        f"{title}\n\n"
        f"Струны E A D G B e\n"
        f"Лады: {strings}\n\n"
        "X — не играть, 0 — открытая струна."
    )
