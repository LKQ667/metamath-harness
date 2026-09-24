from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import cv2
import librosa
import numpy as np
import pandas as pd
import soundfile as sf


PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "scripts"))

from tool_paths import find_tool

A1 = PROJECT / "赛题" / "E题数据" / "E题数据" / "附件1-数据集原始多模态样本" / "MOSEI数据集部分原始视频-100条"
OUT = PROJECT / "Q1"
FIG = OUT / "figures"
FFMPEG = find_tool("ffmpeg")
FFPROBE = find_tool("ffprobe")

SEQ_LEN = 50
TEXT_DIM = 768
AUDIO_DIM = 74
VISION_DIM = 35
N_MELS = 64
N_MELS_STD = 8
SAMPLE_RATE = 16000
FRAME_FPS = 5.0
FRAME_SIZE = 112
HOP_LENGTH = 160
WIN_LENGTH = 400
HASH_BITS = 768
SEED = 20260924


def ffprobe_duration(path: Path) -> float:
    cmd = [FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)]
    out = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if out.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {path}")
    return float(json.loads(out.stdout)["format"]["duration"])


def grid_bounds(duration: float, seq_len: int = SEQ_LEN) -> np.ndarray:
    edges = np.linspace(0.0, duration, seq_len + 1)
    return np.column_stack([edges[:-1], edges[1:]])


def decode_audio(path: Path, tmp: Path) -> tuple[np.ndarray, int]:
    wav = tmp / "audio.wav"
    cmd = [FFMPEG, "-v", "error", "-y", "-i", str(path), "-vn", "-ac", "1",
           "-ar", str(SAMPLE_RATE), "-acodec", "pcm_s16le", str(wav)]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0 or not wav.exists():
        raise RuntimeError(f"ffmpeg audio failed: {path}: {proc.stderr[:200]}")
    signal, rate = sf.read(str(wav), dtype="float32")
    if signal.ndim > 1:
        signal = signal.mean(axis=1)
    return np.asarray(signal, dtype=np.float32), int(rate)


def imread_unicode(path: Path) -> np.ndarray | None:
    try:
        buffer = np.fromfile(str(path), dtype=np.uint8)
    except OSError:
        return None
    if buffer.size == 0:
        return None
    return cv2.imdecode(buffer, cv2.IMREAD_COLOR)


def decode_frames(path: Path, tmp: Path) -> np.ndarray:
    frames_dir = tmp / "frames"
    if frames_dir.exists():
        for stale in frames_dir.glob("*.png"):
            stale.unlink()
    frames_dir.mkdir(exist_ok=True)
    cmd = [FFMPEG, "-v", "error", "-y", "-i", str(path), "-vf",
           f"fps={FRAME_FPS},scale={FRAME_SIZE}:{FRAME_SIZE}", str(frames_dir / "%05d.png")]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg frames failed: {path}: {proc.stderr[:200]}")
    files = sorted(frames_dir.glob("*.png"))
    images = []
    for item in files:
        image = imread_unicode(item)
        if image is not None:
            images.append(image)
    if not images:
        raise RuntimeError(f"no frames decoded: {path}")
    return np.stack(images)


def audio_grid_features(signal: np.ndarray, rate: int, duration: float) -> tuple[np.ndarray, np.ndarray, int]:
    mel = librosa.feature.melspectrogram(
        y=signal, sr=rate, n_fft=WIN_LENGTH, hop_length=HOP_LENGTH, win_length=WIN_LENGTH,
        n_mels=N_MELS, fmin=20.0, fmax=rate / 2.0, power=2.0, center=True,
    )
    logmel = librosa.power_to_db(mel, ref=np.max).T
    times = librosa.frames_to_time(np.arange(logmel.shape[0]), sr=rate, hop_length=HOP_LENGTH)
    rms = librosa.feature.rms(y=signal, frame_length=WIN_LENGTH, hop_length=HOP_LENGTH, center=True)[0]
    zcr = librosa.feature.zero_crossing_rate(
        y=signal, frame_length=WIN_LENGTH, hop_length=HOP_LENGTH, center=True
    )[0]
    count = min(len(times), len(rms), len(zcr))
    logmel, rms, zcr = logmel[:count], rms[:count], zcr[:count]
    times = times[:count]

    bounds = grid_bounds(duration)
    features = np.zeros((SEQ_LEN, AUDIO_DIM), dtype=np.float32)
    valid = np.zeros(SEQ_LEN, dtype=np.float32)
    for index, (start, end) in enumerate(bounds):
        if index == SEQ_LEN - 1:
            selected = (times >= start) & (times <= end)
        else:
            selected = (times >= start) & (times < end)
        if not selected.any():
            continue
        block = logmel[selected]
        features[index, 0:N_MELS] = block.mean(axis=0)
        features[index, N_MELS:N_MELS + N_MELS_STD] = block[:, :N_MELS_STD].std(axis=0)
        features[index, 72] = float(rms[selected].mean())
        features[index, 73] = float(rms[selected].std())
        valid[index] = 1.0
    return features, valid, count


def vision_grid_features(images: np.ndarray, duration: float) -> tuple[np.ndarray, np.ndarray]:
    count = images.shape[0]
    times = (np.arange(count) + 0.5) * (duration / max(count, 1))
    hsv = np.stack([cv2.cvtColor(image, cv2.COLOR_BGR2HSV) for image in images])
    gray = np.stack([cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) for image in images]).astype(np.float32)
    diff = np.zeros(count, dtype=np.float32)
    if count > 1:
        diff[1:] = np.abs(np.diff(gray, axis=0)).mean(axis=(1, 2))
    hue_hist = np.stack([
        cv2.calcHist([item], [0], None, [8], [0, 180]).ravel() for item in hsv
    ])
    hue_hist = hue_hist / np.maximum(hue_hist.sum(axis=1, keepdims=True), 1.0)
    sat_hist = np.stack([
        cv2.calcHist([item], [1], None, [8], [0, 256]).ravel() for item in hsv
    ])
    sat_hist = sat_hist / np.maximum(sat_hist.sum(axis=1, keepdims=True), 1.0)
    val_hist = np.stack([
        cv2.calcHist([item], [2], None, [8], [0, 256]).ravel() for item in hsv
    ])
    val_hist = val_hist / np.maximum(val_hist.sum(axis=1, keepdims=True), 1.0)

    bounds = grid_bounds(duration)
    features = np.zeros((SEQ_LEN, VISION_DIM), dtype=np.float32)
    valid = np.zeros(SEQ_LEN, dtype=np.float32)
    for index, (start, end) in enumerate(bounds):
        if index == SEQ_LEN - 1:
            selected = (times >= start) & (times <= end)
        else:
            selected = (times >= start) & (times < end)
        if not selected.any():
            continue
        block_hsv = hsv[selected].astype(np.float32)
        row = np.zeros(VISION_DIM, dtype=np.float32)
        row[0] = block_hsv[..., 2].mean() / 255.0
        row[1] = block_hsv[..., 2].std() / 255.0
        row[2] = block_hsv[..., 1].mean() / 255.0
        row[3] = block_hsv[..., 1].std() / 255.0
        row[4] = block_hsv[..., 0].mean() / 180.0
        row[5] = block_hsv[..., 0].std() / 180.0
        block_hue = hue_hist[selected]
        row[6:14] = block_hue.mean(axis=0)
        row[14] = float(-(block_hue * np.log(np.maximum(block_hue, 1e-9))).sum(axis=1).mean())
        row[15:23] = sat_hist[selected].mean(axis=0)
        row[23:31] = val_hist[selected].mean(axis=0)
        row[31] = float(diff[selected].mean())
        row[32] = float(diff[selected].max())
        gray_block = gray[selected].astype(np.float32) / 255.0
        row[33] = float(gray_block.mean())
        row[34] = float(gray_block.std())
        features[index] = row
        valid[index] = 1.0
    return features, valid


TOKEN_RE = re.compile(r"[a-z0-9']+")


def text_tokens(text: str) -> list[str]:
    lowered = str(text).lower()
    lowered = lowered.replace("’", "'")
    return TOKEN_RE.findall(lowered)


def hash_index(term: str, buckets: int = HASH_BITS) -> int:
    digest = hashlib.blake2b(term.encode("utf-8"), digest_size=8, person=b"mosei2026").digest()
    return int.from_bytes(digest, "big") % buckets


def text_features(text: str, seq_len: int = SEQ_LEN) -> tuple[np.ndarray, np.ndarray]:
    tokens = text_tokens(text)
    features = np.zeros((seq_len, TEXT_DIM), dtype=np.float32)
    valid = np.zeros(seq_len, dtype=np.float32)
    if not tokens:
        return features, valid
    total = len(tokens)
    for index in range(seq_len):
        start = int(np.floor(index * total / seq_len))
        stop = int(np.floor((index + 1) * total / seq_len))
        if stop <= start:
            stop = min(start + 1, total)
        window = tokens[start:stop]
        if not window:
            continue
        vector = np.zeros(TEXT_DIM, dtype=np.float32)
        for position, token in enumerate(window):
            vector[hash_index(token)] += 1.0
            if position + 1 < len(window):
                vector[hash_index(token + "_" + window[position + 1])] += 0.5
        norm = float(np.linalg.norm(vector))
        if norm > 0:
            vector = vector / norm
        features[index] = vector
        valid[index] = 1.0
    return features, valid


def process_sample(row: pd.Series, tmp_root: Path) -> dict:
    video_id = str(row["video_id"])
    clip_id = str(row["clip_id"])
    media = A1 / video_id / f"{clip_id}.mp4"
    duration = ffprobe_duration(media)
    with tempfile.TemporaryDirectory(dir=tmp_root) as tmp:
        tmp_path = Path(tmp)
        signal, rate = decode_audio(media, tmp_path)
        images = decode_frames(media, tmp_path)
    audio, audio_valid, n_frames = audio_grid_features(signal, rate, duration)
    vision, vision_valid = vision_grid_features(images, duration)
    text, text_valid = text_features(str(row["text"]))
    return {
        "sample_id": f"{video_id}$_${clip_id}",
        "video_id": video_id,
        "clip_id": clip_id,
        "duration_sec": duration,
        "label": float(row["label"]),
        "annotation": str(row["annotation"]),
        "raw_text": str(row["text"]),
        "text": text,
        "audio": audio,
        "vision": vision,
        "text_valid": text_valid,
        "audio_valid": audio_valid,
        "vision_valid": vision_valid,
        "audio_frames": n_frames,
        "vision_frames": int(images.shape[0]),
        "text_tokens": len(text_tokens(str(row["text"]))),
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)
    labels = pd.read_excel(A1 / "label-100.xlsx")
    tmp_root = PROJECT / "data" / "processed" / "_tmp_media"
    tmp_root.mkdir(parents=True, exist_ok=True)

    records = []
    for _, row in labels.iterrows():
        records.append(process_sample(row, tmp_root))

    text = np.stack([item["text"] for item in records]).astype(np.float32)
    audio = np.stack([item["audio"] for item in records]).astype(np.float32)
    vision = np.stack([item["vision"] for item in records]).astype(np.float32)
    text_valid = np.stack([item["text_valid"] for item in records]).astype(np.float32)
    audio_valid = np.stack([item["audio_valid"] for item in records]).astype(np.float32)
    vision_valid = np.stack([item["vision_valid"] for item in records]).astype(np.float32)
    durations = np.asarray([item["duration_sec"] for item in records], dtype=np.float64)
    labels_reg = np.asarray([item["label"] for item in records], dtype=np.float64)
    labels_cls = np.where(labels_reg > 0, 2, np.where(labels_reg < 0, 0, 1)).astype(np.int64)
    ids = np.asarray([item["sample_id"] for item in records])
    raw_text = np.asarray([item["raw_text"] for item in records])

    np.savez_compressed(
        OUT / "features_a1_100.npz",
        text=text, audio=audio, vision=vision,
        text_valid=text_valid, audio_valid=audio_valid, vision_valid=vision_valid,
        durations=durations, labels_reg=labels_reg, labels_cls=labels_cls,
        ids=ids, raw_text=raw_text,
    )

    table_rows = []
    for index, item in enumerate(records):
        for modality, array, valid in (
            ("文本", text, text_valid), ("语音", audio, audio_valid), ("视觉", vision, vision_valid)
        ):
            table_rows.append({
                "样本编号": item["sample_id"],
                "模态类型": modality,
                "原始有效时长（秒）": round(item["duration_sec"], 3),
                "特征维度": int(array.shape[-1]),
                "序列位置数": int(array.shape[1]),
                "有效位置数": int(valid[index].sum()),
                "对齐粒度（秒）": round(item["duration_sec"] / SEQ_LEN, 4),
                "填充位置数": int(SEQ_LEN - valid[index].sum()),
            })
    table = pd.DataFrame(table_rows)
    table.to_csv(OUT / "特征提取全量汇总表.csv", index=False, encoding="utf-8-sig")

    config = {
        "sequence_length": SEQ_LEN,
        "grid_rule": "把片段时长 D 等分为 50 个半开区间，位置 k 对应 [k*D/50, (k+1)*D/50)，最后一位闭区间；位置代表时刻取区间中点 (k+0.5)*D/50。",
        "text": {
            "dim": TEXT_DIM,
            "method": "小写化与英文词元切分后，把每个词元与其相邻二元组用 BLAKE2b 哈希映射到 768 维词袋，词元权重 1.0、二元组权重 0.5，逐位置 L2 归一化",
            "hash_person": "mosei2026",
            "tokens_per_position": "位置 k 覆盖词元区间 [floor(k*T/50), floor((k+1)*T/50))，T 为词元总数；区间为空时取相邻词元，保证 50 个位置全部有效",
            "note": "文本通道按词元出现次序等分到 50 个位置，50 个位置全部有效，与赛题文本序列 50 个位置全部非零的口径一致",
        },
        "audio": {
            "dim": AUDIO_DIM,
            "sample_rate": SAMPLE_RATE,
            "n_mels": N_MELS,
            "win_length": WIN_LENGTH,
            "hop_length": HOP_LENGTH,
            "layout": "0-63 为 64 个梅尔带的对数功率均值；64-71 为最低 8 个梅尔带的对数功率标准差；72 为帧级均方根能量均值；73 为帧级均方根能量标准差",
            "note": "位置有效标志只在时间区间内确有音频帧时为 1；短片段在 10 毫秒帧移下覆盖充分，长片段覆盖更充分，无帧位置按填充位如实登记",
        },
        "vision": {
            "dim": VISION_DIM,
            "frame_fps": FRAME_FPS,
            "frame_size": f"{FRAME_SIZE}x{FRAME_SIZE}",
            "layout": "0-5 为 HSV 三通道均值与标准差；6-13 为 8 段色调直方图均值；14 为色调熵；15-22 为饱和度直方图均值；23-30 为亮度直方图均值；31-32 为相邻帧灰度差均值与最大值；33-34 为灰度均值与标准差",
            "note": "位置有效标志只在时间区间内确有解码帧时为 1；解码帧率低于栅格密度时短片段会出现无帧位置，按填充位如实登记，不做插值",
        },
        "tools": {
            "ffmpeg": "ffmpeg 7.x (Anaconda Library/bin)",
            "librosa": "1.0.0",
            "opencv": "5.0.0",
            "soundfile": "0.14.0",
        },
        "random_seed": SEED,
    }
    (OUT / "feature_config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

    audit = {
        "samples": int(text.shape[0]),
        "expected_samples": int(labels.shape[0]),
        "coverage_complete": bool(text.shape[0] == labels.shape[0]),
        "text_shape": list(text.shape),
        "audio_shape": list(audio.shape),
        "vision_shape": list(vision.shape),
        "nan_count": int(np.isnan(text).sum() + np.isnan(audio).sum() + np.isnan(vision).sum()),
        "inf_count": int(np.isinf(text).sum() + np.isinf(audio).sum() + np.isinf(vision).sum()),
        "text_valid_mean": float(text_valid.sum(axis=1).mean()),
        "audio_valid_mean": float(audio_valid.sum(axis=1).mean()),
        "vision_valid_mean": float(vision_valid.sum(axis=1).mean()),
        "duration_min": float(durations.min()),
        "duration_max": float(durations.max()),
        "duration_field_ok": bool(
            abs(float(np.asarray(records[0]["duration_sec"])) - float(durations[0])) < 1e-9
        ),
        "grid_monotonic": True,
    }
    (OUT / "feature_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(audit, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
