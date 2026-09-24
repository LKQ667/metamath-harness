from __future__ import annotations

import json
import os
import pickle
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "scripts"))

from tool_paths import find_tool

RAW = PROJECT / "赛题" / "E题数据" / "E题数据"
A1 = RAW / "附件1-数据集原始多模态样本" / "MOSEI数据集部分原始视频-100条"
A2 = RAW / "附件2-数据集特征文件"
A3 = RAW / "附件3-模态缺失特征样本"
A4 = RAW / "附件4-可解释专项视频样本与特征文件" / "附件4-可解释专项视频样本与特征文件"

DATA_RAW = PROJECT / "data" / "raw"
DATA_PROC = PROJECT / "data" / "processed"

FFPROBE = find_tool("ffprobe")
SEQ_LEN = 50
POSITION_ZERO_IS_PAD = True


def ensure_dirs() -> None:
    DATA_RAW.mkdir(parents=True, exist_ok=True)
    DATA_PROC.mkdir(parents=True, exist_ok=True)


def probe_media(path: Path) -> dict:
    if not path.exists():
        return {"exists": False}
    cmd = [
        FFPROBE, "-v", "error", "-show_entries",
        "format=duration:stream=codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels",
        "-of", "json", str(path),
    ]
    out = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if out.returncode != 0:
        return {"exists": True, "probe_ok": False, "error": out.stderr.strip()[:200]}
    info = json.loads(out.stdout)
    fmt = info.get("format", {})
    streams = info.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), {})
    audio = next((s for s in streams if s.get("codec_type") == "audio"), {})
    fps = video.get("r_frame_rate", "0/1")
    try:
        num, den = fps.split("/")
        fps_value = float(num) / float(den) if float(den) else 0.0
    except Exception:
        fps_value = 0.0
    return {
        "exists": True,
        "probe_ok": True,
        "duration_sec": float(fmt.get("duration", 0.0)),
        "video_codec": video.get("codec_name"),
        "width": video.get("width"),
        "height": video.get("height"),
        "fps": round(fps_value, 4),
        "audio_codec": audio.get("codec_name"),
        "sample_rate": audio.get("sample_rate"),
        "channels": audio.get("channels"),
    }


def build_label_csv() -> tuple[pd.DataFrame, pd.DataFrame]:
    a1 = pd.read_excel(A1 / "label-100.xlsx")
    a2 = pd.read_excel(A2 / "label.xlsx")
    a1.to_csv(DATA_RAW / "label100.csv", index=False, encoding="utf-8-sig")
    a2.to_csv(DATA_RAW / "label_a2.csv", index=False, encoding="utf-8-sig")
    return a1, a2


def build_media_inventory(a1: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in a1.iterrows():
        video_id = str(row["video_id"])
        clip_id = str(row["clip_id"])
        media = A1 / video_id / f"{clip_id}.mp4"
        info = probe_media(media)
        rows.append({
            "video_id": video_id,
            "clip_id": clip_id,
            "sample_id": f"{video_id}$_${clip_id}",
            "media_relpath": f"赛题/E题数据/E题数据/附件1-数据集原始多模态样本/MOSEI数据集部分原始视频-100条/{video_id}/{clip_id}.mp4",
            "label": float(row["label"]),
            "annotation": str(row["annotation"]),
            "text_chars": len(str(row["text"])),
            "text_words": len(str(row["text"]).split()),
            **info,
        })
    inventory = pd.DataFrame(rows)
    inventory.to_csv(DATA_RAW / "a1_media_inventory.csv", index=False, encoding="utf-8-sig")
    return inventory


def load_aligned() -> dict:
    with open(A2 / "aligned_50.pkl", "rb") as handle:
        return pickle.load(handle, encoding="latin1")


def build_aligned_npz(aligned: dict) -> dict:
    arrays: dict[str, np.ndarray] = {}
    stats: dict[str, dict] = {}
    for split in ("train", "valid", "test"):
        part = aligned[split]
        arrays[f"{split}_text"] = np.asarray(part["text"], dtype=np.float32)
        arrays[f"{split}_audio"] = np.asarray(part["audio"], dtype=np.float32)
        arrays[f"{split}_vision"] = np.asarray(part["vision"], dtype=np.float32)
        arrays[f"{split}_text_bert"] = np.asarray(part["text_bert"], dtype=np.int32)
        arrays[f"{split}_cls"] = np.asarray(part["classification_labels"], dtype=np.float32)
        arrays[f"{split}_reg"] = np.asarray(part["regression_labels"], dtype=np.float32)
        arrays[f"{split}_ids"] = np.asarray([str(item) for item in part["id"]])
        stats[split] = {
            "n": int(arrays[f"{split}_text"].shape[0]),
            "text_shape": list(arrays[f"{split}_text"].shape),
            "audio_shape": list(arrays[f"{split}_audio"].shape),
            "vision_shape": list(arrays[f"{split}_vision"].shape),
            "cls_counts": {
                "negative": int((arrays[f"{split}_cls"] == 0).sum()),
                "neutral": int((arrays[f"{split}_cls"] == 1).sum()),
                "positive": int((arrays[f"{split}_cls"] == 2).sum()),
            },
            "reg_min": float(arrays[f"{split}_reg"].min()),
            "reg_max": float(arrays[f"{split}_reg"].max()),
            "reg_mean": float(arrays[f"{split}_reg"].mean()),
            "reg_std": float(arrays[f"{split}_reg"].std()),
        }
    np.savez_compressed(DATA_PROC / "mosei_aligned.npz", **arrays)
    return stats


def valid_mask(seq: np.ndarray) -> np.ndarray:
    energy = np.abs(np.asarray(seq, dtype=np.float64)).reshape(len(seq), -1).sum(axis=1)
    return energy > 0


def mask_segments(mask: np.ndarray) -> list[list[int]]:
    segments: list[list[int]] = []
    for index, keep in enumerate(mask):
        if keep:
            continue
        if segments and index == segments[-1][1] + 1:
            segments[-1][1] = index
        else:
            segments.append([index, index])
    return segments


def build_a3_mask() -> pd.DataFrame:
    rows = []
    files = sorted((A3 / "对齐版本").glob("*.pkl"))
    for path in files:
        with open(path, "rb") as handle:
            part = pickle.load(handle, encoding="latin1")["test"]
        sample = path.stem
        entry = {"sample": sample, "file": path.name}
        for modality, key in (("text", "text_bert"), ("audio", "audio"), ("vision", "vision")):
            arr = np.asarray(part[key], dtype=np.float64)
            seq = arr[0].T if key == "text_bert" else arr[0]
            keep = valid_mask(seq)
            segments = mask_segments(keep)
            observed = [seg for seg in segments if not (POSITION_ZERO_IS_PAD and seg == [0, 0])]
            missing_len = int(sum(seg[1] - seg[0] + 1 for seg in observed))
            entry[f"{modality}_valid_len"] = int(keep.sum())
            entry[f"{modality}_missing_len"] = missing_len
            entry[f"{modality}_missing_segments"] = json.dumps(observed)
            entry[f"{modality}_missing_ratio"] = round(missing_len / SEQ_LEN, 4)
        rows.append(entry)
    frame = pd.DataFrame(rows)
    frame.to_csv(DATA_PROC / "a3_missing_mask.csv", index=False, encoding="utf-8-sig")
    return frame


def build_a4_npz() -> dict:
    arrays: dict[str, np.ndarray] = {}
    ids = []
    raw_text = []
    for path in sorted((A4 / "对齐版本").glob("*.pkl")):
        with open(path, "rb") as handle:
            part = pickle.load(handle, encoding="latin1")
        ids.append(str(part["id"]))
        raw_text.append(str(part["raw_text"]))
        arrays.setdefault("text", []).append(np.asarray(part["text"], dtype=np.float32))
        arrays.setdefault("audio", []).append(np.asarray(part["audio"], dtype=np.float32))
        arrays.setdefault("vision", []).append(np.asarray(part["vision"], dtype=np.float32))
        arrays.setdefault("text_bert", []).append(np.asarray(part["text_bert"], dtype=np.int32))
    out = {key: np.stack(value) for key, value in arrays.items()}
    out["ids"] = np.asarray(ids)
    out["raw_text"] = np.asarray(raw_text)
    np.savez_compressed(DATA_PROC / "a4_aligned.npz", **out)
    return {"n": int(out["text"].shape[0]), "text_shape": list(out["text"].shape),
            "audio_shape": list(out["audio"].shape), "vision_shape": list(out["vision"].shape),
            "has_raw_text": True}


def modality_stats(name: str, array: np.ndarray, split: str) -> dict:
    flat = np.asarray(array, dtype=np.float64)
    per_sample_mean = flat.reshape(flat.shape[0], -1).mean(axis=1)
    per_sample_std = flat.reshape(flat.shape[0], -1).std(axis=1)
    dim_var = flat.reshape(-1, flat.shape[-1]).var(axis=0)
    return {
        "split": split,
        "modality": name,
        "shape": list(flat.shape),
        "global_mean": float(flat.mean()),
        "global_std": float(flat.std()),
        "global_min": float(flat.min()),
        "global_max": float(flat.max()),
        "zero_ratio": float((flat == 0).mean()),
        "sample_mean_min": float(per_sample_mean.min()),
        "sample_mean_max": float(per_sample_mean.max()),
        "sample_mean_std": float(per_sample_mean.std()),
        "sample_std_mean": float(per_sample_std.mean()),
        "dim_var_min": float(dim_var.min()),
        "dim_var_max": float(dim_var.max()),
        "dim_var_median": float(np.median(dim_var)),
        "dead_dims": int((dim_var < 1e-12).sum()),
        "n_dims": int(dim_var.shape[0]),
    }


def build_eda_summary(aligned: dict, stats: dict, inventory: pd.DataFrame, a3: pd.DataFrame, a4: dict) -> dict:
    modalities = {"text": "text", "audio": "audio", "vision": "vision"}
    modality_rows = []
    for split in ("train", "valid", "test"):
        for name, key in modalities.items():
            modality_rows.append(modality_stats(name, aligned[split][key], split))

    label_rows = []
    for split in ("train", "valid", "test"):
        reg = np.asarray(aligned[split]["regression_labels"], dtype=np.float64)
        cls = np.asarray(aligned[split]["classification_labels"], dtype=np.float64)
        label_rows.append({
            "split": split,
            "n": int(reg.shape[0]),
            "reg_mean": float(reg.mean()),
            "reg_std": float(reg.std()),
            "reg_skew": float(((reg - reg.mean()) ** 3).mean() / max(reg.std() ** 3, 1e-12)),
            "negative": int((cls == 0).sum()),
            "neutral": int((cls == 1).sum()),
            "positive": int((cls == 2).sum()),
            "neutral_ratio": float((cls == 1).mean()),
        })

    correlations = {}
    for split in ("train",):
        text = np.asarray(aligned[split]["text"], dtype=np.float64).reshape(len(aligned[split]["text"]), -1)
        audio = np.asarray(aligned[split]["audio"], dtype=np.float64).reshape(len(aligned[split]["audio"]), -1)
        vision = np.asarray(aligned[split]["vision"], dtype=np.float64).reshape(len(aligned[split]["vision"]), -1)
        reg = np.asarray(aligned[split]["regression_labels"], dtype=np.float64)
        pooled = {
            "text": text.mean(axis=1),
            "audio": audio.mean(axis=1),
            "vision": vision.mean(axis=1),
        }
        correlations[split] = {
            "text_audio": float(np.corrcoef(pooled["text"], pooled["audio"])[0, 1]),
            "text_vision": float(np.corrcoef(pooled["text"], pooled["vision"])[0, 1]),
            "audio_vision": float(np.corrcoef(pooled["audio"], pooled["vision"])[0, 1]),
            "text_reg": float(np.corrcoef(pooled["text"], reg)[0, 1]),
            "audio_reg": float(np.corrcoef(pooled["audio"], reg)[0, 1]),
            "vision_reg": float(np.corrcoef(pooled["vision"], reg)[0, 1]),
        }

    a3_missing = {
        "n_samples": int(a3.shape[0]),
        "per_modality": {
            modality: {
                "mean_missing_ratio": float(a3[f"{modality}_missing_ratio"].mean()),
                "max_missing_ratio": float(a3[f"{modality}_missing_ratio"].max()),
                "min_missing_ratio": float(a3[f"{modality}_missing_ratio"].min()),
                "samples_with_missing": int((a3[f"{modality}_missing_len"] > 0).sum()),
            }
            for modality in ("text", "audio", "vision")
        },
        "audio_vision_mask_identical": bool(
            (a3["audio_missing_segments"] == a3["vision_missing_segments"]).all()
        ),
        "position_zero_is_pad": POSITION_ZERO_IS_PAD,
    }

    duration = inventory["duration_sec"].astype(float)
    return {
        "sequence_length": SEQ_LEN,
        "attachments": {
            "a1_samples": int(inventory.shape[0]),
            "a1_video_folders": int(inventory["video_id"].nunique()),
            "a1_duration_min": float(duration.min()),
            "a1_duration_max": float(duration.max()),
            "a1_duration_mean": float(duration.mean()),
            "a1_duration_median": float(duration.median()),
            "a1_media_missing": int((~inventory["exists"]).sum()),
            "a1_probe_failed": int((inventory.get("probe_ok", pd.Series([True] * len(inventory))).fillna(False) == False).sum()),
            "a1_annotation_counts": inventory["annotation"].value_counts().to_dict(),
            "a1_text_words_mean": float(inventory["text_words"].mean()),
            "a1_text_words_min": int(inventory["text_words"].min()),
            "a1_text_words_max": int(inventory["text_words"].max()),
            "a2_splits": stats,
            "a3": a3_missing,
            "a4": a4,
        },
        "modality_stats": modality_rows,
        "label_stats": label_rows,
        "modality_correlation": correlations,
    }


def main() -> int:
    ensure_dirs()
    a1, _ = build_label_csv()
    inventory = build_media_inventory(a1)
    aligned = load_aligned()
    stats = build_aligned_npz(aligned)
    a3 = build_a3_mask()
    a4 = build_a4_npz()
    summary = build_eda_summary(aligned, stats, inventory, a3, a4)
    (DATA_PROC / "eda_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({
        "ok": True,
        "a1": summary["attachments"]["a1_samples"],
        "a2": {k: v["n"] for k, v in stats.items()},
        "a3": summary["attachments"]["a3"]["n_samples"],
        "a4": a4["n"],
        "outputs": [
            "data/raw/label100.csv", "data/raw/label_a2.csv", "data/raw/a1_media_inventory.csv",
            "data/processed/mosei_aligned.npz", "data/processed/a3_missing_mask.csv",
            "data/processed/a4_aligned.npz", "data/processed/eda_summary.json",
        ],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
