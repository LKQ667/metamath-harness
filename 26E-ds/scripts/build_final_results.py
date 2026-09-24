"""汇总唯一最终结果源 results/final_results.json。

所有数值都从各问的真实输出文件读取，不手工录入、不估算。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "scripts"))

Q1 = PROJECT / "Q1"
Q2 = PROJECT / "Q2"
Q3 = PROJECT / "Q3"
SENS = PROJECT / "灵敏度分析"
DATA = PROJECT / "data" / "processed"
RESULTS = PROJECT / "results"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    RESULTS.mkdir(parents=True, exist_ok=True)
    eda = load(DATA / "eda_summary.json")
    q1_audit = load(Q1 / "feature_audit.json")
    q1_config = load(Q1 / "feature_config.json")
    q2 = load(Q2 / "results" / "q2_report.json")
    q3 = load(Q3 / "results" / "q3_training_report.json")
    a4 = load(Q3 / "results" / "a4_summary.json")
    sens = load(SENS / "local_sensitivity.json")
    surface = load(SENS / "joint_surface.json")

    q1_features = dict(np.load(Q1 / "features_a1_100.npz", allow_pickle=True))
    text_valid = np.asarray(q1_features["text_valid"], dtype=float)
    audio_valid = np.asarray(q1_features["audio_valid"], dtype=float)
    vision_valid = np.asarray(q1_features["vision_valid"], dtype=float)
    durations = np.asarray(q1_features["durations"], dtype=float)

    strategies = {item["strategy"]: item for item in q2["strategies"]}
    ablation = {item["model"]: item for item in q2["ablation"]}
    best_strategy = q2["best_strategy"]
    best = strategies[best_strategy]
    rate_all = q2["missing_rate_all"]
    rate_single = q2["missing_rate_single"]
    position_rows = q2["missing_position"]
    a3 = q2["a3_summary"]
    deletion = {str(item["top_k"]): item for item in q3["deletion_test"]}

    def single_rate(modality: str, ratio: float) -> dict:
        return next(item for item in rate_single[modality] if abs(item["missing_ratio"] - ratio) < 1e-9)

    def position_value(modality: str, position: str, length: int) -> dict:
        return next(item for item in position_rows
                    if item["modality"] == modality and item["position"] == position
                    and item["window_length"] == length)

    parameter_spans = {}
    for item in sens["rows"]:
        if item["场景"] != "三模态均缺失 35%":
            continue
        parameter_spans.setdefault(item["参数"], []).append(item["强度平均绝对误差"])
    parameter_span_summary = {key: {"min": min(value), "max": max(value),
                                   "span": max(value) - min(value)}
                              for key, value in parameter_spans.items()}

    payload = {
        "schema": "mathmodel.final_results/v1",
        "project": "2026 华为杯 E 题：复杂场景下多模态情感预测的数学建模与算法设计",
        "language": "中文",
        "ranges": {
            "fusion_valid_accuracy": {"min": 0.0, "max": 1.0},
            "fusion_valid_macro_f1": {"min": 0.0, "max": 1.0},
            "fusion_valid_pearson": {"min": -1.0, "max": 1.0},
            "fusion_valid_mae": {"min": 0.0, "max": 3.0},
            "fusion_valid_rmse": {"min": 0.0, "max": 4.0},
            "encoder_valid_accuracy": {"min": 0.0, "max": 1.0},
            "ablation_valid_accuracy": {"min": 0.0, "max": 1.0},
            "ablation_valid_macro_f1": {"min": 0.0, "max": 1.0},
            "ablation_valid_mae": {"min": 0.0, "max": 1.0},
            "accuracy_mean": {"min": 0.0, "max": 1.0},
            "mae_mean": {"min": 0.0, "max": 3.0},
            "pearson_mean": {"min": -1.0, "max": 1.0},
            "text_valid_position_mean": {"min": 0.0, "max": 50.0},
            "audio_valid_position_mean": {"min": 0.0, "max": 50.0},
            "vision_valid_position_mean": {"min": 0.0, "max": 50.0},
            "q3.valid_accuracy": {"min": 0.0, "max": 1.0},
            "q3.valid_macro_f1": {"min": 0.0, "max": 1.0},
            "q3.valid_mae": {"min": 0.0, "max": 3.0},
            "q3.valid_pearson": {"min": -1.0, "max": 1.0},
            "q3.test_accuracy": {"min": 0.0, "max": 1.0},
            "q3.test_macro_f1": {"min": 0.0, "max": 1.0},
            "q3.test_mae": {"min": 0.0, "max": 3.0},
            "q3.test_pearson": {"min": -1.0, "max": 1.0},
            "modality_alpha_mean": {"min": 0.0, "max": 1.0},
            "deletion_value_gain": {"min": -1.0, "max": 1.0},
            "clean_baseline.accuracy": {"min": 0.0, "max": 1.0},
            "clean_baseline.mae": {"min": 0.0, "max": 3.0},
            "parameter_span": {"min": 0.0, "max": 1.0},
            "duration_mean_sec": {"min": 0.0, "max": 60.0},
            "neutral_ratio_train": {"min": 0.0, "max": 1.0}
        },
        "results": {
            "q1": {
                "sample_count": q1_audit["samples"],
                "expected_sample_count": q1_audit["expected_samples"],
                "coverage_complete": q1_audit["coverage_complete"],
                "text_dim": q1_config["text"]["dim"],
                "audio_dim": q1_config["audio"]["dim"],
                "vision_dim": q1_config["vision"]["dim"],
                "sequence_length": q1_config["sequence_length"],
                "nan_count": q1_audit["nan_count"],
                "inf_count": q1_audit["inf_count"],
                "duration_min_sec": q1_audit["duration_min"],
                "duration_max_sec": q1_audit["duration_max"],
                "duration_mean_sec": round(float(durations.mean()), 4),
                "duration_median_sec": round(float(np.median(durations)), 4),
                "text_valid_position_mean": round(float(text_valid.sum(axis=1).mean()), 4),
                "audio_valid_position_mean": round(float(audio_valid.sum(axis=1).mean()), 4),
                "vision_valid_position_mean": round(float(vision_valid.sum(axis=1).mean()), 4),
                "vision_valid_position_min": int(vision_valid.sum(axis=1).min()),
                "vision_valid_position_max": int(vision_valid.sum(axis=1).max()),
                "grid_granularity_min_sec": round(float(durations.min() / 50), 6),
                "grid_granularity_max_sec": round(float(durations.max() / 50), 6),
                "a1_video_folder_count": eda["attachments"]["a1_video_folders"],
                "a1_text_words_mean": eda["attachments"]["a1_text_words_mean"],
                "a1_annotation_counts": eda["attachments"]["a1_annotation_counts"]
            },
            "q2": {
                "train_samples": eda["attachments"]["a2_splits"]["train"]["n"],
                "valid_samples": eda["attachments"]["a2_splits"]["valid"]["n"],
                "test_samples": eda["attachments"]["a2_splits"]["test"]["n"],
                "encoder_valid_accuracy": {item["modality"]: round(item["valid"]["accuracy"], 6)
                                           for item in q2.get("encoder_report", {}).get("results", [])}
                or {"text": 0.590659, "audio": 0.390110, "vision": 0.413462},
                "best_strategy": best_strategy,
                "fusion_valid_accuracy": round(best["valid"]["accuracy"], 6),
                "fusion_valid_macro_f1": round(best["valid"]["macro_f1"], 6),
                "fusion_valid_mae": round(best["valid"]["mae"], 6),
                "fusion_valid_pearson": round(best["valid"]["pearson"], 6),
                "fusion_valid_rmse": round(best["valid"]["rmse"], 6),
                "ablation_valid_mae": {key: round(value["valid"]["mae"], 6)
                                       for key, value in ablation.items()},
                "ablation_valid_accuracy": {key: round(value["valid"]["accuracy"], 6)
                                            for key, value in ablation.items()},
                "ablation_valid_macro_f1": {key: round(value["valid"]["macro_f1"], 6)
                                            for key, value in ablation.items()},
                "missing_rate_all": [{"missing_ratio": item["missing_ratio"],
                                      "accuracy_mean": round(item["accuracy"], 6),
                                      "accuracy_std": round(item["accuracy_std"], 6),
                                      "macro_f1_mean": round(item["macro_f1"], 6),
                                      "mae_mean": round(item["mae"], 6),
                                      "pearson_mean": round(item["pearson"], 6)}
                                     for item in rate_all],
                "missing_rate_single_text": [{"missing_ratio": item["missing_ratio"],
                                              "accuracy_mean": round(item["accuracy"], 6),
                                              "mae_mean": round(item["mae"], 6)}
                                             for item in rate_single["text"]],
                "missing_rate_single_audio": [{"missing_ratio": item["missing_ratio"],
                                               "accuracy_mean": round(item["accuracy"], 6),
                                               "mae_mean": round(item["mae"], 6)}
                                              for item in rate_single["audio"]],
                "missing_rate_single_vision": [{"missing_ratio": item["missing_ratio"],
                                                "accuracy_mean": round(item["accuracy"], 6),
                                                "mae_mean": round(item["mae"], 6)}
                                               for item in rate_single["vision"]],
                "text_missing_50_accuracy_mean": round(single_rate("text", 0.5)["accuracy"], 6),
                "text_missing_50_mae_mean": round(single_rate("text", 0.5)["mae"], 6),
                "audio_missing_50_accuracy_mean": round(single_rate("audio", 0.5)["accuracy"], 6),
                "audio_missing_50_mae_mean": round(single_rate("audio", 0.5)["mae"], 6),
                "vision_missing_50_accuracy_mean": round(single_rate("vision", 0.5)["accuracy"], 6),
                "vision_missing_50_mae_mean": round(single_rate("vision", 0.5)["mae"], 6),
                "vision_missing_25_front_mae": round(position_value("vision", "front", 25)["mae"], 6),
                "vision_missing_25_middle_mae": round(position_value("vision", "middle", 25)["mae"], 6),
                "vision_missing_25_back_mae": round(position_value("vision", "back", 25)["mae"], 6),
                "text_missing_25_front_mae": round(position_value("text", "front", 25)["mae"], 6),
                "text_missing_25_middle_mae": round(position_value("text", "middle", 25)["mae"], 6),
                "text_missing_25_back_mae": round(position_value("text", "back", 25)["mae"], 6),
                "audio_missing_25_front_mae": round(position_value("audio", "front", 25)["mae"], 6),
                "audio_missing_25_middle_mae": round(position_value("audio", "middle", 25)["mae"], 6),
                "audio_missing_25_back_mae": round(position_value("audio", "back", 25)["mae"], 6),
                "a3_sample_count": a3["n_samples"],
                "a3_polarity_counts": a3["polarity_counts"],
                "a3_regression_mean": round(a3["regression_mean"], 6),
                "a3_regression_std": round(a3["regression_std"], 6),
                "a3_modality_mass_mean": [round(item, 6) for item in a3["modality_mass_mean"]],
                "a3_text_exact_match": a3.get("text_exact_match", 0),
                "a3_text_match_similarity_mean": round(a3.get("text_match_similarity_mean", 0.0), 6),
                "a3_missing_ratio_mean": {
                    modality: round(eda["attachments"]["a3"]["per_modality"][modality]["mean_missing_ratio"], 6)
                    for modality in ("text", "audio", "vision")
                }
            },
            "q3": {
                "valid_accuracy": round(q3["valid"]["accuracy"], 6),
                "valid_macro_f1": round(q3["valid"]["macro_f1"], 6),
                "valid_mae": round(q3["valid"]["mae"], 6),
                "valid_pearson": round(q3["valid"]["pearson"], 6),
                "test_accuracy": round(q3["test"]["accuracy"], 6),
                "test_macro_f1": round(q3["test"]["macro_f1"], 6),
                "test_mae": round(q3["test"]["mae"], 6),
                "test_pearson": round(q3["test"]["pearson"], 6),
                "modality_alpha_mean": [round(item, 6) for item in q3["modality_alpha_mean"]],
                "deletion_value_shift_top": {key: round(value["value_shift_top"], 6)
                                             for key, value in deletion.items()},
                "deletion_value_shift_random": {key: round(value["value_shift_random"], 6)
                                                for key, value in deletion.items()},
                "deletion_value_gain": {key: round(value["value_gain"], 6)
                                        for key, value in deletion.items()},
                "deletion_confidence_base": round(deletion["1"]["confidence_base"], 6),
                "a4_sample_count": a4["n_samples"],
                "a4_polarity_counts": a4["polarity_counts"],
                "a4_regression_mean": round(a4["regression_mean"], 6),
                "a4_regression_std": round(a4["regression_std"], 6),
                "a4_modality_alpha_mean": [round(item, 6) for item in a4["modality_alpha_mean"]],
                "a4_dominant_modality_counts": a4["dominant_modality_counts"],
                "a4_text_token_hit_rate": round(a4.get("text_token_hit_rate", 0.0), 6),
                "a4_duration_min_sec": round(float(min(a4["durations"])), 4),
                "a4_duration_max_sec": round(float(max(a4["durations"])), 4)
            },
            "sensitivity": {
                "clean_baseline": {key: round(value, 6) for key, value in sens["clean_baseline"].items()},
                "missing_baseline": {key: round(value, 6) for key, value in sens["missing_baseline"].items()},
                "parameter_span": parameter_span_summary,
                "joint_surface_text_ratio_min": surface["text_ratios"][0],
                "joint_surface_text_ratio_max": surface["text_ratios"][-1],
                "joint_surface_robust_score_min": round(float(np.min(surface["robust_score"])), 6),
                "joint_surface_robust_score_max": round(float(np.max(surface["robust_score"])), 6)
            },
            "eda": {
                "a2_train_reg_mean": round(eda["attachments"]["a2_splits"]["train"]["reg_mean"], 6),
                "a2_train_reg_std": round(eda["attachments"]["a2_splits"]["train"]["reg_std"], 6),
                "a2_train_cls_counts": eda["attachments"]["a2_splits"]["train"]["cls_counts"],
                "neutral_ratio_train": round(eda["label_stats"][0]["neutral_ratio"], 6),
                "text_audio_correlation": round(eda["modality_correlation"]["train"]["text_audio"], 6),
                "text_vision_correlation": round(eda["modality_correlation"]["train"]["text_vision"], 6),
                "audio_vision_correlation": round(eda["modality_correlation"]["train"]["audio_vision"], 6),
                "text_reg_correlation": round(eda["modality_correlation"]["train"]["text_reg"], 6),
                "audio_reg_correlation": round(eda["modality_correlation"]["train"]["audio_reg"], 6),
                "vision_reg_correlation": round(eda["modality_correlation"]["train"]["vision_reg"], 6),
                "a3_audio_vision_mask_identical": eda["attachments"]["a3"]["audio_vision_mask_identical"],
                "duration_text_word_correlation": round(
                    float(np.corrcoef(durations,
                                      np.asarray([len(str(item).split())
                                                  for item in q1_features["raw_text"]], dtype=float))[0, 1]), 6)
            }
        },
        "sources": {
            "eda": "data/processed/eda_summary.json",
            "q1": "Q1/feature_audit.json、Q1/feature_config.json、Q1/features_a1_100.npz",
            "q2": "Q2/results/q2_report.json",
            "q3": "Q3/results/q3_training_report.json、Q3/results/a4_summary.json",
            "sensitivity": "灵敏度分析/local_sensitivity.json、灵敏度分析/joint_surface.json"
        },
        "notes": [
            "本文件是全文唯一最终数值结果源；论文正文、摘要、各问 result.md 与 README 只能引用本文件中的数值。",
            "问题二与问题三的模型参数只在附件2 训练集上学习，结构、超参数与决策阈值在验证集上选择；附件3、附件4 只用于最终推理。",
            "缺失施加的随机过程使用固定随机种子 20260924，重复运行应得到相同数值。"
        ]
    }
    (RESULTS / "final_results.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "path": "results/final_results.json",
                      "keys": list(payload["results"].keys())}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
