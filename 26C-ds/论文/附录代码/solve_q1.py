from __future__ import annotations
import sys as _sys
_sys.dont_write_bytecode = True
try:
    _sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
import json
import sys
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
from scipy import optimize, stats
PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / 'scripts'))
sys.path.insert(0, str(PROJECT / '数据预处理'))
import eeg_lib as E
import plot_common as P
from compare_denoise import artifact_suppression
FS = E.FS
N_BASE = int(round(E.EPOCH_PRE * FS))
P300 = slice(N_BASE + int(round(0.25 * FS)), N_BASE + int(round(0.5 * FS)))
EARLY = slice(N_BASE + int(round(0.08 * FS)), N_BASE + int(round(0.25 * FS)))
LATE = slice(N_BASE + int(round(0.25 * FS)), N_BASE + int(round(0.8 * FS)))
DATASET_CN = {'A1': 'A组项目一', 'A2': 'A组项目二', 'B1': 'B组项目一', 'B2': 'B组项目二'}

def gaussian_sum(t, *params):
    out = np.full_like(t, params[0])
    for k in range(3):
        amp, mu, sigma = params[1 + 3 * k:4 + 3 * k]
        out = out + amp * np.exp(-(t - mu) ** 2 / (2.0 * sigma ** 2))
    return out

def fit_components(t, erp):
    seeds = [(0.1, 0.05), (0.2, 0.07), (0.35, 0.1)]
    scale = float(np.percentile(np.abs(erp), 95)) or 1.0
    p0, lo, hi = ([float(np.median(erp[:N_BASE]))], [-3 * scale], [3 * scale])
    for mu, sigma in seeds:
        p0 += [scale * 0.5, mu, sigma]
        lo += [-5 * scale, max(mu - 0.08, 0.01), 0.02]
        hi += [5 * scale, mu + 0.1, 0.3]
    popt, pcov = optimize.curve_fit(gaussian_sum, t, erp, p0=p0, bounds=(lo, hi), maxfev=60000)
    fitted = gaussian_sum(t, *popt)
    ss_res = float(np.sum((erp - fitted) ** 2))
    ss_tot = float(np.sum((erp - erp.mean()) ** 2))
    perr = np.sqrt(np.diag(pcov)) if pcov is not None else np.full(len(popt), np.nan)
    comps = []
    for k in range(3):
        amp, mu, sigma = popt[1 + 3 * k:4 + 3 * k]
        eamp = perr[1 + 3 * k]
        comps.append({'amplitude_uV': round(float(amp), 4), 'amplitude_se_uV': round(float(eamp), 4), 'latency_ms': round(float(mu) * 1000, 2), 'width_ms': round(float(sigma) * 1000, 2)})
    comps.sort(key=lambda c: c['latency_ms'])
    return {'components': comps, 'r2': round(1.0 - ss_res / ss_tot, 5) if ss_tot > 0 else None, 'rmse_uV': round(float(np.sqrt(ss_res / erp.size)), 4), 'baseline_uV': round(float(popt[0]), 4), 'fitted': fitted}

def bootstrap_peak(epochs, window):
    n = epochs.shape[0]
    peaks = epochs[:, window].mean(axis=1)
    idx = int(np.argmax(np.abs(peaks)))
    vals = epochs[:, window.start + idx]
    point, lo, hi = E.bootstrap_ci(vals)
    return {'amplitude_uV': round(point, 4), 'ci95_low': round(lo, 4), 'ci95_high': round(hi, 4)}

def load_epochs(key):
    d = np.load(PROJECT / 'data' / 'derived' / f'epochs_{key}.npz')
    return d

def figure_erp(t, curves, out_dir):
    font = P.apply_style(8.0)
    fig, ax = P.new_figure(89.0, 68.0)
    colors = {'Fz': P.PALETTE['blue_main'], 'F3': P.PALETTE['teal_main'], 'F4': P.PALETTE['orange_main']}
    for ch in ('Fz', 'F3', 'F4'):
        erp = curves[ch]['erp']
        ax.plot(t * 1000, erp, color=colors[ch], lw=1.5, label=f'{ch} 导联', zorder=3)
    for ch in ('Fz', 'F3', 'F4'):
        ax.plot(t * 1000, curves[ch]['fitted'], color=colors[ch], lw=1.0, ls=(0, (5, 3)), alpha=0.85, zorder=2)
    ax.plot([], [], color=P.PALETTE['neutral_dark'], lw=1.0, ls=(0, (5, 3)), label='三高斯分量拟合')
    ax.axvspan(250, 500, color=P.PALETTE['gold_main'], alpha=0.14, lw=0, zorder=0)
    ax.axvline(0, color=P.PALETTE['neutral_mid'], lw=0.8, ls=':', zorder=1)
    ax.axhline(0, color=P.PALETTE['neutral_light'], lw=0.7, zorder=1)
    ax.set_xlim(-200, 1000)
    ax.set_xticks([-200, 0, 250, 500, 750, 1000])
    top = float(max((np.max(curves[ch]['erp']) for ch in curves))) * 1.34
    bot = float(min((np.min(curves[ch]['erp']) for ch in curves)))
    ax.set_ylim(bot - 0.08 * (top - bot), top)
    P.style_axes(ax, '刺激后时间 / ms', '幅值 / μV', grid_axis='y')
    ax.text(375, bot - 0.02 * (top - bot), 'P300 窗', ha='center', va='bottom', fontsize=7, color=P.PALETTE['neutral_dark'])
    ax.legend(loc='upper left', ncol=2, handlelength=1.8, columnspacing=1.0, labelspacing=0.32)
    paths = P.export(fig, out_dir, 'fig1_erp_curve')
    return (paths, font)

def figure_interval(per_dataset, out_dir):
    font = P.apply_style(8.0)
    fig = plt.figure(figsize=(P.mm_to_inch(89.0), P.mm_to_inch(62.0)))
    ax = fig.add_axes([0.22, 0.17, 0.75, 0.7])
    keys = ['A1', 'A2', 'B1', 'B2']
    off = 0.15
    for i, key in enumerate(keys):
        rec = per_dataset[key]
        for j, (tag, color, label) in enumerate((('raw', P.PALETTE['neutral_mid'], '去噪前'), ('den', P.PALETTE['blue_main'], '去噪后'))):
            vals = rec[tag]
            med = float(np.median(vals))
            lo, hi = np.percentile(vals, [5, 95])
            y = i + (off if j else -off)
            ax.plot([lo, hi], [y, y], color=color, lw=1.5, solid_capstyle='round')
            ax.plot([lo, lo], [y - 0.055, y + 0.055], color=color, lw=1.0)
            ax.plot([hi, hi], [y - 0.055, y + 0.055], color=color, lw=1.0)
            ax.scatter([med], [y], s=24, color=color, zorder=3, label=label if i == 0 else None)
    ax.set_yticks(np.arange(len(keys)))
    ax.set_yticklabels([DATASET_CN[k] for k in keys])
    ax.set_ylim(len(keys) - 0.45, -0.45)
    ax.set_xscale('log')
    P.style_axes(ax, '单试次峰值幅值 / μV', '', grid_axis='x')
    ax.legend(loc='lower left', bbox_to_anchor=(0.0, 1.01), ncol=2, handlelength=1.3)
    paths = P.export(fig, out_dir, 'fig2_artifact_interval')
    return (paths, font)

def figure_count(counts, out_dir):
    font = P.apply_style(8.0)
    fig = plt.figure(figsize=(P.mm_to_inch(89.0), P.mm_to_inch(62.0)))
    ax = fig.add_axes([0.15, 0.19, 0.82, 0.68])
    keys = ['A1', 'A2', 'B1', 'B2']
    x = np.arange(len(keys))
    width = 0.36
    clipped = [counts[k]['clipped_samples'] for k in keys]
    saturated = [counts[k]['saturated_samples'] for k in keys]
    b1 = ax.bar(x - width / 2, clipped, width, color=P.PALETTE['blue_main'], label='软截断采样点')
    b2 = ax.bar(x + width / 2, saturated, width, color=P.PALETTE['orange_main'], label='设备饱和采样点')
    for bars in (b1, b2):
        for rect in bars:
            h = rect.get_height()
            ax.annotate(f'{h:.0f}', (rect.get_x() + rect.get_width() / 2, h), xytext=(0, 2), textcoords='offset points', ha='center', va='bottom', fontsize=6.5)
    ax.set_xticks(x)
    ax.set_xticklabels([DATASET_CN[k] for k in keys])
    ax.set_ylim(0, max(max(clipped), max(saturated)) * 1.22)
    P.style_axes(ax, '', '采样点计数', grid_axis='y')
    ax.legend(loc='upper left', bbox_to_anchor=(0.0, 1.01), ncol=2, handlelength=1.3)
    paths = P.export(fig, out_dir, 'fig3_artifact_count')
    return (paths, font)

def main() -> int:
    out_dir = PROJECT / 'Q1' / 'figures'
    out_dir.mkdir(parents=True, exist_ok=True)
    t = E.time_axis()
    results = {'stage': 'q1', 'figure_style_font': P.apply_style(8.0), 'datasets': {}}
    per_dataset_curves, per_dataset_peak, counts = ({}, {}, {})
    fitted_curves = {}
    for spec in E.DATASETS:
        key = spec['key']
        d = load_epochs(key)
        cue = d['cue']
        entry = {'task_cn': spec['task_cn'], 'group': spec['group'], 'channels': {}}
        raw_peaks, den_peaks = ([], [])
        for ch in E.EEG_CHANNELS:
            raw = d[f'raw_{ch}'].astype(float)
            den = d[f'den_{ch}'].astype(float)
            raw_peaks.append(np.max(np.abs(raw), axis=1))
            den_peaks.append(np.max(np.abs(den), axis=1))
            erp = den.mean(axis=0)
            fit = fit_components(t, erp)
            pvals = E.pointwise_ttest(den, N_BASE)
            mask = E.fdr_mask(pvals, 0.05)
            post = slice(N_BASE, N_BASE + int(round(0.8 * FS)))
            cond = {}
            for label, tag in ((-1, 'left'), (1, 'right')):
                sel = cue == label
                cond[tag] = {'trials': int(sel.sum()), 'p300': bootstrap_peak(den[sel], P300), 'early': bootstrap_peak(den[sel], EARLY), 'late_mean_uV': round(float(den[sel][:, LATE].mean()), 4), 'reliability': round(float(np.corrcoef(den[sel][0::2].mean(0)[N_BASE:], den[sel][1::2].mean(0)[N_BASE:])[0, 1]), 4)}
            entry['channels'][ch] = {'raw_peak_99_uV': round(float(np.percentile(np.max(np.abs(raw), axis=1), 99)), 3), 'denoised_peak_99_uV': round(float(np.percentile(np.max(np.abs(den), axis=1), 99)), 3), 'artifact_suppression_ratio': round(artifact_suppression(raw, den), 4), 'significant_points_post800': int(np.count_nonzero(mask[post])), 'p300_window_ms': [250, 500], 'gaussian_fit': {k: v for k, v in fit.items() if k != 'fitted'}, 'left': cond['left'], 'right': cond['right'], 'laterality_index': round((cond['right']['p300']['amplitude_uV'] - cond['left']['p300']['amplitude_uV']) / (abs(cond['right']['p300']['amplitude_uV']) + abs(cond['left']['p300']['amplitude_uV']) + 1e-09), 4)}
            fitted_curves.setdefault(key, {})[ch] = {'erp': erp, 'fitted': fit['fitted']}
        results['datasets'][key] = entry
        per_dataset_curves[key] = fitted_curves[key]
        per_dataset_peak[key] = {'raw': np.concatenate(raw_peaks), 'den': np.concatenate(den_peaks)}
        print(f'[{key}] 拟合 R²=' + ' '.join((f'{ch}:{entry['channels'][ch]['gaussian_fit']['r2']}' for ch in E.EEG_CHANNELS)))
    audit = json.loads((PROJECT / '数据预处理' / 'audit.json').read_text(encoding='utf-8'))
    for spec in E.DATASETS:
        key = spec['key']
        rec = E.load_record(PROJECT, spec['file'])
        on, _cv = E.event_onsets(rec['data'][E.CUE_INDEX])
        tot_clip = 0
        tot_sat = 0
        for ch in E.EEG_CHANNELS:
            from sweep_denoise import clip_extremes
            ep = E.baseline_correct(E.epoch_matrix(rec['data'][E.EEG_INDEX[ch]], on))
            _s2, n_clip = clip_extremes(ep, 10.0)
            tot_clip += int(n_clip)
            tot_sat += int(np.count_nonzero(np.abs(rec['data'][E.EEG_INDEX[ch]]) >= 1000.0))
        counts[key] = {'clipped_samples': tot_clip, 'saturated_samples': tot_sat}
        results['datasets'][key]['denoise_counts'] = counts[key]
    results['audit_operations'] = audit['operations']
    fig_curve = fitted_curves['A2']
    p1, font = figure_erp(t, fig_curve, out_dir)
    p2, _ = figure_interval(per_dataset_peak, out_dir)
    p3, _ = figure_count(counts, out_dir)
    results['figures'] = {'fig1_erp_curve': {'paths': [str(p.relative_to(PROJECT)).replace('\\', '/') for p in p1], 'dataset_shown': 'A2', 'note': '曲线取自 A 组项目二记录，该记录响应最强'}, 'fig2_artifact_interval': {'paths': [str(p.relative_to(PROJECT)).replace('\\', '/') for p in p2]}, 'fig3_artifact_count': {'paths': [str(p.relative_to(PROJECT)).replace('\\', '/') for p in p3]}}
    results['figure_style_font'] = font
    E.save_json(PROJECT / 'results' / 'q1_results.json', results)
    print('已写入 results/q1_results.json 与 Q1/figures/')
    return 0
if __name__ == '__main__':
    raise SystemExit(main())
