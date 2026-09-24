from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import torch

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "scripts"))
sys.path.insert(0, str(PROJECT / "Q3"))
sys.path.insert(0, str(PROJECT / "Q2"))

from tool_paths import find_tool

import mm_data as md
from model_q3 import build_interpretable
from run_q2 import encode_raw
from text_features import text_features
from train_q3 import infer, load_cache, tensors

OUT = PROJECT / "Q3"
CACHE = PROJECT / "Q2" / "cache"
RESULTS = OUT / "results"
A4 = PROJECT / "赛题" / "E题数据" / "E题数据" / "附件4-可解释专项视频样本与特征文件" / "附件4-可解释专项视频样本与特征文件" / "对齐版本"
FFPROBE = find_tool("ffprobe")
DEVICE = torch.device("cpu")
MODALITIES = md.MODALITIES
SEQ_LEN = md.SEQ_LEN
POLARITY = np.asarray(["Negative", "Neutral", "Positive"])


def duration_of(path: Path) -> float:
    cmd = [FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)]
    out = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if out.returncode != 0:
        return float("nan")
    return float(json.loads(out.stdout)["format"]["duration"])


def segments_of(mask: np.ndarray) -> list[list[int]]:
    out: list[list[int]] = []
    for index, keep in enumerate(mask):
        if keep:
            continue
        if out and index == out[-1][1] + 1:
            out[-1][1] = index
        else:
            out.append([index, index])
    return out


def text_embedding_lookup(aligned: dict) -> dict:
    """建立 BERT 词元编号到连续文本表示的查表：键为单个位置的三元组，值为该位置 768 维表示。"""
    table: dict[bytes, np.ndarray] = {}
    for split in md.SPLITS:
        tokens = np.asarray(aligned[f"{split}_text_bert"], dtype=np.int64)
        text = np.asarray(aligned[f"{split}_text"], dtype=np.float32)
        for index in range(tokens.shape[0]):
            for position in range(tokens.shape[2]):
                key = tokens[index, :, position].tobytes()
                table.setdefault(key, text[index, position])
    return table


def text_from_tokens(tokens: np.ndarray, table: dict, norm: dict, n: int) -> tuple[np.ndarray, float]:
    """按词元编号逐位置查表得到连续文本表示；未命中的位置取全体已匹配表示的均值。"""
    features = np.zeros((n, SEQ_LEN, md.DIMS["text"]), dtype=np.float32)
    fallback = np.mean(np.stack(list(table.values())), axis=0)
    hit = 0
    total = 0
    for row in range(n):
        for position in range(SEQ_LEN):
            key = tokens[row, :, position].tobytes()
            value = table.get(key)
            total += 1
            if value is not None:
                features[row, position] = value
                hit += 1
            else:
                features[row, position] = fallback
    return md.normalize(features, "text", norm), hit / max(total, 1)


def main() -> int:
    parser = argparse.ArgumentParser(description="附件 4 可解释推理与解释文件产出")
    parser.add_argument("--hidden", type=int, default=192)
    args = parser.parse_args()

    RESULTS.mkdir(parents=True, exist_ok=True)
    model = build_interpretable(args.hidden).to(DEVICE)
    model.load_state_dict(torch.load(RESULTS / "interpretable_model.pt", map_location=DEVICE))

    data = np.load(PROJECT / "data" / "processed" / "a4_aligned.npz", allow_pickle=True)
    aligned = md.load_aligned()
    stats = np.load(CACHE / "norm_stats.npz")
    norm = {m: {"mean": stats[f"{m}_mean"], "std": stats[f"{m}_std"]} for m in MODALITIES}
    reference = md.quantile_reference(aligned)

    n = data["audio"].shape[0]
    lookup = text_embedding_lookup(aligned)
    text_norm, text_hit_rate = text_from_tokens(np.asarray(data["text_bert"], dtype=np.int64), lookup, norm, n)
    audio_norm = md.rank_map(data["audio"], "audio", reference, norm)
    vision_norm = md.rank_map(data["vision"], "vision", reference, norm)

    encoded = {
        "text": encode_raw(text_norm, "text"),
        "audio": encode_raw(audio_norm, "audio"),
        "vision": encode_raw(vision_norm, "vision"),
    }
    sequences = [torch.from_numpy(encoded[m]).float() for m in MODALITIES]
    masks = [torch.ones(n, SEQ_LEN),
             torch.from_numpy(md.valid_mask(data["audio"])).float(),
             torch.from_numpy(md.valid_mask(data["vision"])).float()]

    output = infer(model, sequences, masks)
    prob = torch.softmax(torch.from_numpy(output["logits"]), dim=1).numpy()
    cls = prob.argmax(axis=1)
    alpha = output["alpha"]
    beta = output["beta"]
    contribution = output["contribution"]

    durations = []
    for index in range(n):
        video = A4 / "videos" / f"{index + 1:02d}.mp4"
        durations.append(duration_of(video) if video.exists() else float("nan"))

    prediction_rows = []
    evidence_rows = []
    for index in range(n):
        duration = durations[index]
        sample_id = str(data["ids"][index])
        order = np.argsort(-beta[index])[:5]
        dominant = int(np.argmax(alpha[index]))
        prediction_rows.append({
            "样本编号": sample_id,
            "情感极性预测": str(POLARITY[cls[index]]),
            "极性置信度": round(float(prob[index, cls[index]]), 4),
            "情感强度预测": round(float(output["regression"][index]), 4),
            "主要参考模态": MODALITIES[dominant],
            "文本作用程度": round(float(alpha[index, 0]), 4),
            "语音作用程度": round(float(alpha[index, 1]), 4),
            "视觉作用程度": round(float(alpha[index, 2]), 4),
            "关键证据位置": "、".join(str(int(item) + 1) for item in order),
            "关键证据时间窗": "；".join(
                f"第{int(item) + 1}位[{item * duration / SEQ_LEN:.2f},{ (item + 1) * duration / SEQ_LEN:.2f})秒"
                for item in order
            ),
            "片段时长（秒）": round(float(duration), 3),
            "视觉关键帧": f"第{int(order[0] * duration / SEQ_LEN * 5) + 1}帧（5帧/秒）",
        })
        for position in order:
            per_modality = contribution[index, :, position]
            top_modality = int(np.argmax(per_modality))
            evidence_rows.append({
                "样本编号": sample_id,
                "证据位置": int(position) + 1,
                "证据时间起点（秒）": round(float(position * duration / SEQ_LEN), 3),
                "证据时间终点（秒）": round(float((position + 1) * duration / SEQ_LEN), 3),
                "位置重要性": round(float(beta[index, position]), 4),
                "文本贡献": round(float(per_modality[0]), 4),
                "语音贡献": round(float(per_modality[1]), 4),
                "视觉贡献": round(float(per_modality[2]), 4),
                "该位置主要证据模态": MODALITIES[top_modality],
            })

    import pandas as pd
    pd.DataFrame(prediction_rows).to_csv(OUT / "附件4_预测与解释结果.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(evidence_rows).to_csv(OUT / "附件4_关键证据定位.csv", index=False, encoding="utf-8-sig")

    np.savez_compressed(
        RESULTS / "a4_outputs.npz",
        prob=prob, regression=output["regression"], alpha=alpha, beta=beta,
        contribution=contribution, ids=np.asarray([str(item) for item in data["ids"]]),
        durations=np.asarray(durations),
    )

    modality_alpha = alpha.mean(axis=0)
    dominant_counts = {name: int((alpha.argmax(axis=1) == i).sum()) for i, name in enumerate(MODALITIES)}
    summary = {
        "n_samples": int(n),
        "polarity_counts": {name: int((cls == i).sum()) for i, name in enumerate(POLARITY)},
        "regression_mean": float(output["regression"].mean()),
        "regression_std": float(output["regression"].std()),
        "modality_alpha_mean": modality_alpha.tolist(),
        "dominant_modality_counts": dominant_counts,
        "text_source": "附件4 的 BERT 词元编号与附件 2 同源，文本通道按词元编号在附件 2 中查表得到连续文本表示后编码",
        "text_token_hit_rate": float(text_hit_rate),
        "modality_mapping": "文本通道按词元编号查表；语音与视觉通道按秩映射到附件 2 训练集每个维度的分位分布后标准化，再经冻结编码器编码",
        "durations": [round(float(item), 3) for item in durations],
        "top_evidence_position_hist": np.bincount(beta.argmax(axis=1), minlength=SEQ_LEN).tolist(),
    }
    (RESULTS / "a4_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
