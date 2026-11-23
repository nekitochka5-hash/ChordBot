"""Определение аккордов по аудио.

Зависимости: numpy, scipy и программа ffmpeg (для чтения mp3/m4a/ogg и т.д.).
Принцип работы:
  1. ffmpeg переводит файл в моно 22 кГц.
  2. Считаем «хромаграмму»: сколько энергии в каждой из 12 нот в каждый момент.
  3. Сравниваем с шаблонами мажорных и минорных аккордов.
  4. Алгоритм Витерби сглаживает результат, чтобы аккорды не «дрожали».
"""
import subprocess

import numpy as np
from scipy.ndimage import median_filter

SR = 22050
N_FFT = 8192
HOP = 2048
F_MIN = 82.0      # ~ ми большой октавы (нижняя струна гитары)
F_MAX = 2100.0
MAX_SECONDS = 10 * 60
MIN_SEGMENT = 0.4  # аккорды короче 0.4 сек сливаются с соседними

NOTE_NAMES = ["C", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
NOTE_RU = ["до", "ре♭", "ре", "ми♭", "ми", "фа", "фа♯", "соль", "ля♭", "ля", "си♭", "си"]

# Профили Крумхансла-Кесслера для определения тональности
KEY_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
KEY_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

# Аккорды, которые удобно играть открытыми (для подсказки про каподастр)
OPEN_SHAPES = {"C", "A", "G", "E", "D", "Am", "Em", "Dm"}


def load_audio(path, max_seconds=MAX_SECONDS):
    cmd = ["ffmpeg", "-v", "error", "-i", path, "-t", str(max_seconds),
           "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"]
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
    except FileNotFoundError:
        raise RuntimeError("На сервере не установлен ffmpeg")
    if proc.returncode != 0 or not proc.stdout:
        raise ValueError("Не удалось прочитать аудио. Попробуйте mp3 или wav.")
    return np.frombuffer(proc.stdout, dtype=np.float32).copy()


def compute_chroma(y):
    peak = float(np.abs(y).max())
    if peak < 1e-4:
        raise ValueError("В файле тишина.")
    y = y / peak
    if len(y) < N_FFT:
        y = np.pad(y, (0, N_FFT - len(y)))
    n_frames = 1 + (len(y) - N_FFT) // HOP

    window = np.hanning(N_FFT).astype(np.float32)
    freqs = np.fft.rfftfreq(N_FFT, 1.0 / SR)
    band = (freqs >= F_MIN) & (freqs <= F_MAX)
    f = freqs[band]
    midi = 69.0 + 12.0 * np.log2(f / 440.0)

    spec = np.empty((n_frames, f.size), dtype=np.float32)
    for i in range(n_frames):
        seg = y[i * HOP: i * HOP + N_FFT] * window
        spec[i] = np.abs(np.fft.rfft(seg))[band]

    # Подстройка под строй записи (если гитара/запись сдвинута от 440 Гц)
    avg = spec.mean(axis=0)
    is_peak = np.zeros(avg.shape, dtype=bool)
    is_peak[1:-1] = (avg[1:-1] > avg[:-2]) & (avg[1:-1] > avg[2:]) & (avg[1:-1] > avg.mean())
    dev = midi - np.round(midi)
    z = np.sum(avg[is_peak] * np.exp(2j * np.pi * dev[is_peak]))
    tuning = float(np.angle(z) / (2 * np.pi)) if abs(z) > 0 else 0.0
    pitch_class = np.mod(np.round(midi - tuning).astype(int), 12)

    energy = spec.sum(axis=1)
    comp = np.log1p(spec * (1000.0 / (float(spec.max()) + 1e-9)))
    assign = np.zeros((f.size, 12), dtype=np.float32)
    assign[np.arange(f.size), pitch_class] = 1.0
    chroma = comp @ assign
    chroma = median_filter(chroma, size=(5, 1), mode="nearest")

    norm = np.linalg.norm(chroma, axis=1, keepdims=True)
    chroma_n = chroma / (norm + 1e-9)
    silent = energy < 0.04 * np.percentile(energy, 95)
    return chroma_n, silent, chroma.mean(axis=0)


def build_templates():
    """24 шаблона: 12 мажорных и 12 минорных трезвучий."""
    templates, labels = [], []
    for quality, third in (("maj", 4), ("min", 3)):
        for root in range(12):
            t = np.zeros(12)
            t[root] = 1.0
            t[(root + third) % 12] = 1.0
            t[(root + 7) % 12] = 1.0
            templates.append(t / np.linalg.norm(t))
            labels.append((root, quality))
    return np.array(templates), labels


def viterbi(emission, stay=0.96, beta=12.0):
    n, k = emission.shape
    log_emit = beta * emission
    log_stay = np.log(stay)
    log_switch = np.log((1.0 - stay) / (k - 1))
    dp = np.empty((n, k))
    back = np.empty((n, k), dtype=np.int64)
    dp[0] = log_emit[0]
    back[0] = np.arange(k)
    idx = np.arange(k)
    for t in range(1, n):
        prev = dp[t - 1]
        best = int(prev.argmax())
        switch_score = prev[best] + log_switch
        stay_score = prev + log_stay
        use_stay = stay_score >= switch_score
        dp[t] = np.where(use_stay, stay_score, switch_score) + log_emit[t]
        back[t] = np.where(use_stay, idx, best)
    path = np.empty(n, dtype=np.int64)
    path[-1] = int(dp[-1].argmax())
    for t in range(n - 1, 0, -1):
        path[t - 1] = back[t, path[t]]
    return path


def chord_name(label):
    root, quality = label
    return NOTE_NAMES[root] + ("m" if quality == "min" else "")


def detect_key(mean_chroma):
    best, best_score = None, -2.0
    for root in range(12):
        for mode, profile in (("maj", KEY_MAJOR), ("min", KEY_MINOR)):
            score = np.corrcoef(mean_chroma, np.roll(profile, root))[0, 1]
            if score > best_score:
                best, best_score = (root, mode), score
    root, mode = best
    if mode == "maj":
        return f"{NOTE_NAMES[root]} ({NOTE_RU[root]} мажор)"
    return f"{NOTE_NAMES[root]}m ({NOTE_RU[root]} минор)"


def _segments(path, n_samples, labels):
    n_chord_states = len(labels)
    raw = []
    start = 0
    for i in range(1, len(path) + 1):
        if i == len(path) or path[i] != path[start]:
            raw.append([start, i, int(path[start])])
            start = i

    def to_time(frame):
        return max(0.0, (frame * HOP + N_FFT / 2 - HOP / 2) / SR)

    total = n_samples / SR
    segs = []
    for a, b, state in raw:
        t0 = 0.0 if a == 0 else to_time(a)
        t1 = total if b == len(path) else to_time(b)
        segs.append([t0, t1, state])

    # склеиваем слишком короткие куски с соседями
    changed = True
    while changed and len(segs) > 1:
        changed = False
        for i, (t0, t1, _) in enumerate(segs):
            if t1 - t0 < MIN_SEGMENT:
                if i > 0:
                    segs[i - 1][1] = t1
                else:
                    segs[1][0] = t0
                del segs[i]
                changed = True
                break
        merged = [segs[0]]
        for s in segs[1:]:
            if s[2] == merged[-1][2]:
                merged[-1][1] = s[1]
            else:
                merged.append(s)
        segs = merged

    result = []
    for t0, t1, state in segs:
        if state < n_chord_states:
            result.append({"start": t0, "end": t1, "chord": labels[state]})
    return result


def suggest_capo(segments):
    """Ищем лад каподастра, при котором больше всего аккордов играются открытыми."""
    if not segments:
        return None

    def shape(label, capo):
        return chord_name(((label[0] - capo) % 12, label[1]))

    def score(capo):
        return sum(s["end"] - s["start"] for s in segments if shape(s["chord"], capo) in OPEN_SHAPES)

    total = sum(s["end"] - s["start"] for s in segments)
    base = score(0)
    best_capo, best_score = 0, base
    for capo in range(1, 8):
        sc = score(capo)
        if sc > best_score + 1e-9:
            best_capo, best_score = capo, sc
    if best_capo == 0 or best_score < base + 0.1 * total:
        return None
    seen = []
    for s in segments:
        pair = (chord_name(s["chord"]), shape(s["chord"], best_capo))
        if pair not in seen:
            seen.append(pair)
    return {"fret": best_capo, "pairs": seen[:8]}


def analyze(path):
    y = load_audio(path)
    if len(y) < SR * 3:
        raise ValueError("Файл слишком короткий (меньше 3 секунд).")
    chroma, silent, mean_chroma = compute_chroma(y)
    templates, labels = build_templates()

    sim = chroma @ templates.T                       # (кадры, 24)
    emission = np.zeros((sim.shape[0], 25))
    emission[:, :24] = np.where(silent[:, None], 0.0, sim)
    emission[:, 24] = np.where(silent, 1.0, 0.0)     # состояние «нет аккорда»

    path = viterbi(emission)
    segments = _segments(path, len(y), labels)
    if not segments:
        raise ValueError("Не удалось уверенно определить аккорды.")

    durations = {}
    for s in segments:
        name = chord_name(s["chord"])
        durations[name] = durations.get(name, 0.0) + (s["end"] - s["start"])
    main = [n for n, _ in sorted(durations.items(), key=lambda kv: -kv[1])][:8]

    return {
        "duration": len(y) / SR,
        "key": detect_key(mean_chroma),
        "segments": segments,
        "main_chords": main,
        "capo": suggest_capo(segments),
    }


def _fmt_time(t):
    return f"{int(t // 60)}:{int(t % 60):02d}"


def format_result(res, per_line=8, max_chunk=3500):
    """Готовит текст для Telegram (HTML). Возвращает список сообщений."""
    head = [
        f"🎸 <b>Тональность:</b> {res['key']}",
        f"<b>Основные аккорды:</b> {', '.join(res['main_chords'])}",
    ]
    capo = res["capo"]
    if capo:
        pairs = ", ".join(f"{shape} (вместо {real})" for real, shape in capo["pairs"] if real != shape)
        head.append(f"<b>Каподастр:</b> {capo['fret']}-й лад. Играйте формы: {pairs}")
    head.append("")
    head.append("<b>Аккорды по времени:</b>")

    segs = res["segments"]
    lines = []
    for i in range(0, len(segs), per_line):
        group = segs[i:i + per_line]
        lines.append(f"{_fmt_time(group[0]['start']):>5}  " + "  ".join(chord_name(s["chord"]) for s in group))

    note = ("\nАккорды определены автоматически (мажор/минор). "
            "В сложных местах возможны ошибки — проверяйте на слух.")

    messages, current = [], []
    size = 0
    for line in lines:
        if size + len(line) > max_chunk and current:
            messages.append("<pre>" + "\n".join(current) + "</pre>")
            current, size = [], 0
        current.append(line)
        size += len(line) + 1
    if current:
        messages.append("<pre>" + "\n".join(current) + "</pre>")

    messages[0] = "\n".join(head) + "\n" + messages[0]
    messages[-1] += note
    return messages
