"""探索性数据分析：数据规模、完整性、分布与质量评估。

输出 results/eda_results.json，为数据预处理说明与论文的问题重述提供实测依据。
"""

from __future__ import annotations

import sys as _sys
_sys.dont_write_bytecode = True


import sys
from pathlib import Path

import numpy as np
from scipy import stats

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "scripts"))

import eeg_lib as E  # noqa: E402


def main() -> int:
    report = {"datasets": {}, "summary": {}}
    total_samples = 0
    total_trials = 0
    for spec in E.DATASETS:
        rec = E.load_record(PROJECT, spec["file"])
        x = rec["data"]
        fs = rec["fs"]
        ts = x[E.TS_INDEX]
        cue_on, cue_val = E.event_onsets(x[E.CUE_INDEX])
        act_on, act_val = E.event_onsets(x[E.ACT_INDEX])

        entry = {
            "file": spec["file"],
            "sampling_rate_hz": fs,
            "n_channels": int(x.shape[0]),
            "n_samples": int(x.shape[1]),
            "duration_s": round(float(ts[-1]), 3),
            "labels": rec["labels"],
            "missing_values": int(np.count_nonzero(~np.isfinite(x))),
            "duplicate_timestamps": int(x.shape[1] - np.unique(ts).size),
            "timestamp_step_s": round(float(np.median(np.diff(ts))), 8),
            "trials_cue": int(cue_on.size),
            "trials_action": int(act_on.size),
            "cue_left": int(np.sum(cue_val < 0)),
            "cue_right": int(np.sum(cue_val > 0)),
            "channels": {},
        }
        for ch in E.EEG_CHANNELS:
            v = x[E.EEG_INDEX[ch]]
            entry["channels"][ch] = {
                "mean_uV": round(float(v.mean()), 3),
                "std_uV": round(float(v.std()), 3),
                "robust_scale_uV": round(E.robust_scale(v), 3),
                "min_uV": round(float(v.min()), 2),
                "max_uV": round(float(v.max()), 2),
                "p01_uV": round(float(np.percentile(v, 1)), 2),
                "p99_uV": round(float(np.percentile(v, 99)), 2),
                "kurtosis": round(float(stats.kurtosis(v)), 3),
                "skewness": round(float(stats.skew(v)), 3),
                "saturation_count": int(np.count_nonzero(np.abs(v) >= 1000.0)),
            }
        ecg = x[E.ECG_INDEX]
        entry["ecg"] = {
            "std_uV": round(float(ecg.std()), 3),
            "r_peaks": int(E.r_peaks(ecg).size),
            "heart_rate_bpm": round(float(E.r_peaks(ecg).size / (ts[-1] / 60.0)), 2),
        }
        # 分段后的质量：伪迹试次比例
        flags = {}
        for ch in E.EEG_CHANNELS:
            ep = E.baseline_correct(E.epoch_matrix(x[E.EEG_INDEX[ch]], cue_on))
            f = E.trial_artifact_flags(ep, 6.0)
            flags[ch] = round(float(f.mean()), 4)
        entry["artifact_trial_fraction"] = flags
        entry["cue_action_agreement"] = round(float(np.mean((cue_val[:act_val.size] < 0) == (act_val < 0))), 4)

        report["datasets"][spec["key"]] = entry
        total_samples += int(x.shape[1])
        total_trials += int(cue_on.size)
        print(f"[{spec['key']}] {x.shape[1]} 采样点 × {x.shape[0]} 通道，时长 {ts[-1]:.1f} s，"
              f"试次 {cue_on.size}，伪迹试次比例 {np.mean(list(flags.values())):.3f}")

    report["summary"] = {
        "datasets": len(E.DATASETS),
        "total_samples": total_samples,
        "total_trials": total_trials,
        "total_duration_s": round(sum(v["duration_s"] for v in report["datasets"].values()), 2),
        "any_missing_values": any(v["missing_values"] > 0 for v in report["datasets"].values()),
        "any_duplicate_timestamps": any(v["duplicate_timestamps"] > 0 for v in report["datasets"].values()),
        "any_saturation": any(c["saturation_count"] > 0
                              for v in report["datasets"].values() for c in v["channels"].values()),
        "mean_artifact_trial_fraction": round(float(np.mean(
            [f for v in report["datasets"].values() for f in v["artifact_trial_fraction"].values()])), 4),
    }
    E.save_json(PROJECT / "results" / "eda_results.json", report)
    print("已写入 results/eda_results.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
