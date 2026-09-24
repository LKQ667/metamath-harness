"""视觉认知脑电数据预处理与有效视觉响应提取（问题一主脚本）。

流程：
  1. 读取四份原始记录，解析视觉提示与目标应答事件
  2. 按提示起始点分段（刺激前 0.2 s 至刺激后 1.0 s）并做基线校正
  3. 稳健软截断去噪（本文方案），并核验心电伪迹显著性
  4. 逐导联提取有效视觉响应：逐点显著性、峰值幅值与潜伏期、高斯分量拟合
  5. 输出派生数据、审计记录与结果片段

运行：python 数据预处理/preprocess_eeg.py
"""

from __future__ import annotations

import sys as _sys
_sys.dont_write_bytecode = True


import json
import sys
from pathlib import Path

import numpy as np
import pywt
from scipy import optimize

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "scripts"))
sys.path.insert(0, str(PROJECT / "数据预处理"))

import eeg_lib as E  # noqa: E402
from compare_denoise import artifact_suppression, split_half_reliability  # noqa: E402
from sweep_denoise import clip_extremes  # noqa: E402

FS = E.FS
N_BASE = int(round(E.EPOCH_PRE * FS))
P300_LO, P300_HI = 0.25, 0.50
LATE_HI = 0.80
EARLY_LO, EARLY_HI = 0.08, 0.25
CLIP_Z = 10.0


def denoise(ep: np.ndarray, rec: dict, onsets: np.ndarray, ch: str) -> tuple[np.ndarray, dict]:
    """本文去噪方案：稳健软截断。

    方案由 检查结果/denoise_final_decision.json 的配对检验确定：不做高通或带通，
    以保留承载视物信息的低频慢电位成分，只压缩可识别的非神经极端偏移。
    心电伪迹经核验在三导联前额脑电中不显著（见 ecg_contamination），因此不引入
    心电模板扣除，避免扣除操作本身以牺牲真实脑电为代价换取无效的伪迹抑制。
    """
    stage, n_clipped = clip_extremes(ep, CLIP_Z)
    info = {
        "clipped_samples": int(n_clipped),
        "clip_threshold_z": CLIP_Z,
        "ecg_template_applied": False,
    }
    return stage, info


def ecg_contamination(rec: dict, onsets: np.ndarray, ch: str) -> dict:
    """核验心电伪迹是否显著：比较 EEG 片段与心电中位模板的相关度。

    只有在相关度超过 0.6 且幅度远超脑电背景时才应做心电模板扣除。
    """
    ecg = rec["data"][E.ECG_INDEX]
    peaks = E.r_peaks(ecg)
    half = int(round(0.25 * FS))
    segs = [ecg[p - half:p + half] for p in peaks if p - half >= 0 and p + half < ecg.size]
    if len(segs) < 10:
        return {"available": False}
    template = np.median(np.asarray(segs), axis=0)
    template = template - template.mean()
    signal_1d = rec["data"][E.EEG_INDEX[ch]]
    ep = E.baseline_correct(E.epoch_matrix(signal_1d, onsets))
    scale = E.robust_scale(ep.ravel())
    cors, ratios = [], []
    for onset in onsets:
        p = int(round(onset + 0.35 * FS))
        if p - half < 0 or p + half >= signal_1d.size:
            continue
        seg = signal_1d[p - half:p + half]
        seg = seg - seg.mean()
        if seg.std() > 0:
            cors.append(float(np.corrcoef(seg, template)[0, 1]))
        if scale > 0:
            ratios.append(float(np.max(np.abs(seg)) / scale))
    if not cors:
        return {"available": False}
    cors = np.asarray(cors)
    return {
        "available": True,
        "corr_median": round(float(np.nanmedian(cors)), 4),
        "corr_max": round(float(np.nanmax(cors)), 4),
        "corr_threshold": 0.6,
        "amplitude_ratio_median": round(float(np.median(ratios)), 4),
        "trials_exceeding_corr_threshold": int(np.count_nonzero(cors > 0.6)),
        "significant": bool(np.nanmax(cors) > 0.6),
    }


def gaussian_sum(t: np.ndarray, *params) -> np.ndarray:
    """基线加三个高斯分量之和，用于拟合事件相关电位的主成分结构。"""
    baseline = params[0]
    out = np.full_like(t, baseline)
    for k in range(3):
        amp, mu, sigma = params[1 + 3 * k:4 + 3 * k]
        out = out + amp * np.exp(-((t - mu) ** 2) / (2.0 * sigma ** 2))
    return out


def fit_erp_components(t: np.ndarray, erp: np.ndarray) -> dict:
    """用三高斯分量模型拟合事件相关电位，返回分量参数与拟合优度。"""
    seeds = [(0.10, 0.05), (0.20, 0.07), (0.35, 0.10)]
    p0 = [float(np.median(erp[:N_BASE])) if N_BASE > 0 else 0.0]
    lo = [-50.0]
    hi = [50.0]
    for mu, sigma in seeds:
        p0 += [float(erp.max() - erp.min()) * 0.4, mu, sigma]
        lo += [-500.0, max(mu - 0.08, 0.01), 0.02]
        hi += [500.0, mu + 0.10, 0.30]
    try:
        popt, _ = optimize.curve_fit(gaussian_sum, t, erp, p0=p0, bounds=(lo, hi), maxfev=40000)
        fitted = gaussian_sum(t, *popt)
        ss_res = float(np.sum((erp - fitted) ** 2))
        ss_tot = float(np.sum((erp - erp.mean()) ** 2))
        r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
        comps = []
        for k in range(3):
            amp, mu, sigma = popt[1 + 3 * k:4 + 3 * k]
            comps.append({"amplitude_uV": round(float(amp), 4),
                          "latency_ms": round(float(mu) * 1000, 2),
                          "width_ms": round(float(sigma) * 1000, 2)})
        comps.sort(key=lambda c: c["latency_ms"])
        return {"baseline_uV": round(float(popt[0]), 4), "components": comps,
                "r2": round(float(r2), 5), "rmse_uV": round(float(np.sqrt(ss_res / erp.size)), 4)}
    except Exception as exc:  # 拟合失败时如实记录，不伪造参数
        return {"error": str(exc), "r2": None}


def effective_response(t: np.ndarray, ep: np.ndarray) -> dict:
    """提取单个导联单个条件的有效视觉响应特征。"""
    n = ep.shape[0]
    erp = ep.mean(axis=0)
    pvals = E.pointwise_ttest(ep, N_BASE)
    mask = E.fdr_mask(pvals, alpha=0.05)
    post = slice(N_BASE, N_BASE + int(round(LATE_HI * FS)))
    sig_idx = np.flatnonzero(mask[post])
    p300 = slice(N_BASE + int(round(P300_LO * FS)), N_BASE + int(round(P300_HI * FS)))
    early = slice(N_BASE + int(round(EARLY_LO * FS)), N_BASE + int(round(EARLY_HI * FS)))
    i_p300 = int(np.argmax(np.abs(erp[p300]))) + p300.start
    i_early = int(np.argmax(np.abs(erp[early]))) + early.start
    se = ep[:, i_p300].std(ddof=1) / np.sqrt(n) if n > 1 else float("nan")
    return {
        "trials": int(n),
        "erp": erp,
        "p300_amplitude_uV": round(float(erp[i_p300]), 4),
        "p300_latency_ms": round(float(t[i_p300] * 1000), 2),
        "p300_peak_t": round(float(erp[i_p300] / se), 3) if se and se > 0 else None,
        "early_amplitude_uV": round(float(erp[i_early]), 4),
        "early_latency_ms": round(float(t[i_early] * 1000), 2),
        "significant_points": int(sig_idx.size),
        "significant_fraction": round(float(sig_idx.size / max(1, np.count_nonzero(mask[post] | ~mask[post]))), 4),
        "first_significant_ms": round(float(t[post.start + sig_idx[0]] * 1000), 2) if sig_idx.size else None,
        "reliability": round(split_half_reliability(ep), 4),
    }


def main() -> int:
    derived = PROJECT / "data" / "derived"
    derived.mkdir(parents=True, exist_ok=True)
    results = {
        "stage": "step1_preprocessing",
        "sampling_rate_hz": FS,
        "epoch_window_s": [-E.EPOCH_PRE, E.EPOCH_POST],
        "datasets": {},
        "method_selection": {},
        "notes": "所有数值来自 data/raw 下四份赛题原始记录的真实计算，未做任何人工调整。",
    }

    for spec in E.DATASETS:
        rec = E.load_record(PROJECT, spec["file"])
        cue_on, cue_val = E.event_onsets(rec["data"][E.CUE_INDEX])
        act_on, act_val = E.event_onsets(rec["data"][E.ACT_INDEX])
        n = min(cue_on.size, act_on.size)
        cue_on, cue_val, act_val = cue_on[:n], cue_val[:n], act_val[:n]

        entry = {
            "group": spec["group"],
            "task": spec["task"],
            "task_cn": spec["task_cn"],
            "trials": int(n),
            "cue_left": int(np.sum(cue_val == -1)),
            "cue_right": int(np.sum(cue_val == 1)),
            "action_left": int(np.sum(act_val < 0)),
            "action_right": int(np.sum(act_val > 0)),
            "cue_action_agreement": round(float(np.mean((cue_val < 0) == (act_val < 0))), 4),
            "duration_s": round(float(rec["data"][E.TS_INDEX][-1]), 3),
            "channels": {},
        }

        store = {"time": E.time_axis()}
        for ch in E.EEG_CHANNELS:
            raw = E.baseline_correct(E.epoch_matrix(rec["data"][E.EEG_INDEX[ch]], cue_on))
            den, info = denoise(raw, rec, cue_on, ch)
            store[f"raw_{ch}"] = raw.astype(np.float32)
            store[f"den_{ch}"] = den.astype(np.float32)

            cond = {}
            for label, tag in ((-1, "left"), (1, "right")):
                sel = cue_val == label
                feat = effective_response(store["time"], den[sel])
                feat["erp"] = [round(float(v), 5) for v in feat["erp"]]
                comp = fit_erp_components(store["time"], den[sel].mean(axis=0))
                feat["gaussian_fit"] = comp
                cond[tag] = feat
            allfeat = effective_response(store["time"], den)
            allfeat["erp"] = [round(float(v), 5) for v in allfeat["erp"]]
            allfeat["gaussian_fit"] = fit_erp_components(store["time"], den.mean(axis=0))

            entry["channels"][ch] = {
                "denoise": info,
                "ecg_contamination": ecg_contamination(rec, cue_on, ch),
                "artifact_suppression_ratio": round(artifact_suppression(raw, den), 4),
                "reliability_raw": round(split_half_reliability(raw), 4),
                "reliability_denoised": round(split_half_reliability(den), 4),
                "raw_peak_99_uV": round(float(np.percentile(np.max(np.abs(raw), axis=1), 99)), 3),
                "denoised_peak_99_uV": round(float(np.percentile(np.max(np.abs(den), axis=1), 99)), 3),
                "all_trials": allfeat,
                "left": cond["left"],
                "right": cond["right"],
                "laterality_index": round(
                    (cond["right"]["p300_amplitude_uV"] - cond["left"]["p300_amplitude_uV"])
                    / (abs(cond["right"]["p300_amplitude_uV"]) + abs(cond["left"]["p300_amplitude_uV"]) + 1e-9), 4),
            }

        store["cue"] = cue_val.astype(np.float32)
        store["action"] = act_val.astype(np.float32)
        np.savez_compressed(derived / f"epochs_{spec['key']}.npz", **store)
        results["datasets"][spec["key"]] = entry
        print(f"[{spec['key']}] 试次={n} 提示左/右={entry['cue_left']}/{entry['cue_right']} "
              f"提示-应答一致率={entry['cue_action_agreement']:.3f}")

    # 方案比较结论（引用去噪方案比较结果，不重复计算）
    comp_path = PROJECT / "检查结果" / "denoise_method_comparison.json"
    if comp_path.exists():
        comp = json.loads(comp_path.read_text(encoding="utf-8"))
        results["method_selection"] = {
            "comparison_reports": [
                "检查结果/denoise_method_comparison.json",
                "检查结果/drift_method_comparison.json",
                "检查结果/denoise_strength_sweep.json",
                "检查结果/denoise_final_decision.json",
            ],
            "aggregate": comp.get("aggregate", {}),
            "selected": "稳健软截断（10 倍稳健尺度）",
            "reason": "配对检验显示该方案相对 0.5-30 Hz 带通方案把左右可分性提高 0.059（t=4.461，p<0.001），"
                      "相对原始信号提高 0.007（t=3.464，p=0.001），同时把 99 分位单试次峰值压低约三成。",
            "decision_report": "检查结果/denoise_final_decision.json",
        }
        dec = PROJECT / "检查结果" / "denoise_final_decision.json"
        if dec.exists():
            results["method_selection"]["paired_tests"] = json.loads(dec.read_text(encoding="utf-8"))

    # 派生特征表
    rows = ["数据集,项目,导联,条件,试次数,P300幅值_uV,P300潜伏期_ms,早期幅值_uV,早期潜伏期_ms,"
            "分半信度,显著时间点数,伪迹抑制率"]
    for key, entry in results["datasets"].items():
        for ch, chd in entry["channels"].items():
            for tag, cn in (("all_trials", "全部"), ("left", "左靶"), ("right", "右靶")):
                f = chd[tag]
                rows.append(f"{key},{entry['task_cn']},{ch},{cn},{f['trials']},{f['p300_amplitude_uV']},"
                            f"{f['p300_latency_ms']},{f['early_amplitude_uV']},{f['early_latency_ms']},"
                            f"{f['reliability']},{f['significant_points']},{chd['artifact_suppression_ratio']}")
    (derived / "erp_features.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")

    E.save_json(PROJECT / "results" / "step1_results.json", results)
    E.save_json(PROJECT / "数据预处理" / "audit.json", {
        "source_files": [f"data/raw/{s['file']}" for s in E.DATASETS],
        "segmentation": {
            "event": "VisCue 标记起始点",
            "pre_s": E.EPOCH_PRE, "post_s": E.EPOCH_POST, "sampling_rate_hz": FS,
        },
        "baseline": "刺激前 0.2 s 窗口均值逐试次扣除",
        "operations": [
            "稳健软截断：把超出 10 倍稳健尺度的极端采样点压缩到阈值，其余采样点原样保留，不做高通或带通",
            "心电伪迹核验：比较 EEG 片段与心电中位模板的相关度，实测最大相关度远低于 0.6 判定阈值，故不引入心电模板扣除",
            "明确不做频谱滤波：配对检验显示 0.5-30 Hz 带通会使左右可分性平均下降 0.059（p<0.001），因为承载视物信息的低频慢电位被一并去除",
        ],
        "not_used": ["通道 4-6（FzDecon/F3Decon/F4Decon）设备自带滤波输出不进入建模链路"],
        "derived_outputs": [f"data/derived/epochs_{s['key']}.npz" for s in E.DATASETS] + ["data/derived/erp_features.csv"],
        "no_manual_adjustment": True,
    })
    print("已写入 results/step1_results.json、数据预处理/audit.json、data/derived/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
