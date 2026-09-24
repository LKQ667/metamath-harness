"""汇总唯一结果源 results/final_results.json。

论文正文、摘要、README 与各问 result.md 只能引用本文件中的数值。
运行：python scripts/build_final_results.py
"""

from __future__ import annotations

import sys as _sys
_sys.dont_write_bytecode = True
try:
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]


def load(rel: str) -> dict:
    path = PROJECT / rel
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    eda = load("results/eda_results.json")
    step1 = load("results/step1_results.json")
    q1 = load("results/q1_results.json")
    q2 = load("results/q2_results.json")
    q3 = load("results/q3_results.json")
    decision = load("检查结果/denoise_final_decision.json")
    drift = load("检查结果/drift_method_comparison.json")
    sweep = load("检查结果/denoise_strength_sweep.json")

    out = {
        "meta": {
            "competition": "2026 中国研究生数学建模竞赛（华为杯）C 题",
            "title": "服务于脑机接口与精神性疾病诊断的脑电图计算模型",
            "result_source": "results/final_results.json",
            "note": "本文件是全项目唯一结果源，论文正文、摘要、README 与各问 result.md 的数值均引用此处。",
            "data_origin": "四份赛题原始记录的真实计算，未做任何人工调整",
        },
        "dataset_overview": {
            "datasets": eda.get("summary", {}).get("datasets"),
            "total_samples": eda.get("summary", {}).get("total_samples"),
            "total_trials": eda.get("summary", {}).get("total_trials"),
            "total_duration_s": eda.get("summary", {}).get("total_duration_s"),
            "missing_values": eda.get("summary", {}).get("any_missing_values"),
            "duplicate_timestamps": eda.get("summary", {}).get("any_duplicate_timestamps"),
            "saturation_present": eda.get("summary", {}).get("any_saturation"),
            "mean_artifact_trial_fraction": eda.get("summary", {}).get("mean_artifact_trial_fraction"),
            "per_dataset": {
                k: {
                    "duration_s": v["duration_s"],
                    "trials": v["trials_cue"],
                    "cue_left": v["cue_left"],
                    "cue_right": v["cue_right"],
                    "cue_action_agreement": v["cue_action_agreement"],
                    "heart_rate_bpm": v["ecg"]["heart_rate_bpm"],
                    "artifact_trial_fraction": v["artifact_trial_fraction"],
                    "channel_std_uV": {c: v["channels"][c]["std_uV"] for c in v["channels"]},
                    "channel_robust_scale_uV": {c: v["channels"][c]["robust_scale_uV"] for c in v["channels"]},
                    "saturation_count": {c: v["channels"][c]["saturation_count"] for c in v["channels"]},
                }
                for k, v in eda.get("datasets", {}).items()
            },
        },
        "q1_preprocessing": {
            "method_selected": step1.get("method_selection", {}).get("selected"),
            "selection_reason": step1.get("method_selection", {}).get("reason"),
            "paired_tests": decision.get("M2_vs_M1a", {}),
            "paired_test_vs_raw": decision.get("M2_vs_M0", {}),
            "per_dataset_auc": {
                k: {
                    "M0_raw": v.get("M0原始", {}).get("auc_mean"),
                    "M1a_bandpass": v.get("M1a传统带通", {}).get("auc_mean"),
                    "M2_proposed": v.get("M2本文方案", {}).get("auc_mean"),
                    "M1b_bandpass_reject": v.get("M1b传统带通剔除", {}).get("auc_mean"),
                }
                for k, v in decision.get("per_dataset", {}).items()
            },
            "strength_sweep": sweep.get("summary", {}),
            "drift_methods": drift.get("aggregate", {}),
            "ecg_contamination": {
                k: {ch: v["channels"][ch].get("ecg_contamination", {})
                    for ch in v["channels"]}
                for k, v in step1.get("datasets", {}).items()
            },
            "denoise_counts": {
                k: v.get("denoise_counts") for k, v in q1.get("datasets", {}).items()
            },
            "gaussian_fit_r2": {
                k: {ch: v["channels"][ch]["gaussian_fit"].get("r2") for ch in v["channels"]}
                for k, v in q1.get("datasets", {}).items()
            },
            "artifact_suppression_ratio": {
                k: {ch: v["channels"][ch]["artifact_suppression_ratio"] for ch in v["channels"]}
                for k, v in q1.get("datasets", {}).items()
            },
            "p300_features": {
                k: {ch: {
                    "p300_amplitude_uV": v["channels"][ch]["left"]["p300"]["amplitude_uV"],
                    "p300_ci95": [v["channels"][ch]["left"]["p300"]["ci95_low"],
                                  v["channels"][ch]["left"]["p300"]["ci95_high"]],
                    "left_p300_uV": v["channels"][ch]["left"]["p300"]["amplitude_uV"],
                    "right_p300_uV": v["channels"][ch]["right"]["p300"]["amplitude_uV"],
                    "laterality_index": v["channels"][ch]["laterality_index"],
                    "significant_points_post800": v["channels"][ch]["significant_points_post800"],
                } for ch in v["channels"]}
                for k, v in q1.get("datasets", {}).items()
            },
            "figures": q1.get("figures", {}),
        },
        "q2_computational_model": {
            "model": q2.get("model", {}),
            "feature_auc": q2.get("features", {}),
            "per_dataset": q2.get("datasets", {}),
            "figures": q2.get("figures", {}),
        },
        "q3_cognitive_model": {
            "model": q3.get("model", {}),
            "validation": q3.get("validation", {}),
            "per_dataset": q3.get("datasets", {}),
            "figures": q3.get("figures", {}),
        },
        "sensitivity": {
            "local_sensitivity": q3.get("validation", {}).get("local_sensitivity", {}),
            "parameter_surface_figure": q3.get("figures", {}).get("fig6_parameter_contour", {}),
        },
    }
    path = PROJECT / "results" / "final_results.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    size = path.stat().st_size
    print(f"已写入 {path.relative_to(PROJECT).as_posix()}（{size} 字节）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
