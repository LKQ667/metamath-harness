from __future__ import annotations
import pickle
from pathlib import Path
import numpy as np
PROJECT = Path(__file__).resolve().parents[1]
DATA = PROJECT / 'data' / 'processed'
RAW = PROJECT / '赛题' / 'E题数据' / 'E题数据'
SEQ_LEN = 50
MODALITIES = ('text', 'audio', 'vision')
DIMS = {'text': 768, 'audio': 74, 'vision': 35}
SPLITS = ('train', 'valid', 'test')
AUDIO_SCALE_DIM = 0
EPS = 1e-06

def load_aligned() -> dict:
    return dict(np.load(DATA / 'mosei_aligned.npz', allow_pickle=True))

def _scale_audio_columns(audio: np.ndarray) -> np.ndarray:
    audio = np.asarray(audio, dtype=np.float64)
    audio[..., AUDIO_SCALE_DIM] = np.sign(audio[..., AUDIO_SCALE_DIM]) * np.log1p(np.abs(audio[..., AUDIO_SCALE_DIM]))
    return audio

def normalization_stats(aligned: dict) -> dict:
    stats = {}
    for modality in MODALITIES:
        train = np.asarray(aligned[f'train_{modality}'], dtype=np.float64)
        if modality == 'audio':
            train = _scale_audio_columns(train)
        flat = train.reshape(-1, train.shape[-1])
        mean = flat.mean(axis=0)
        std = flat.std(axis=0)
        std[std < EPS] = 1.0
        stats[modality] = {'mean': mean.astype(np.float64), 'std': std.astype(np.float64)}
    return stats
QUANTILE_GRID = 201

def quantile_reference(aligned: dict) -> dict:
    reference = {}
    grid = np.linspace(0.0, 1.0, QUANTILE_GRID)
    for modality in MODALITIES:
        train = np.asarray(aligned[f'train_{modality}'], dtype=np.float64)
        if modality == 'audio':
            train = _scale_audio_columns(train)
        flat = train.reshape(-1, train.shape[-1])
        reference[modality] = {'grid': grid, 'values': np.quantile(flat, grid, axis=0).astype(np.float64)}
    return reference

def rank_map(array: np.ndarray, modality: str, reference: dict, stats: dict) -> np.ndarray:
    data = np.asarray(array, dtype=np.float64).copy()
    if modality == 'audio':
        data = _scale_audio_columns(data)
    flat = data.reshape(-1, data.shape[-1])
    mask = np.abs(flat).sum(axis=1) > 0
    if mask.sum() == 0:
        return np.zeros_like(data, dtype=np.float32)
    grid = reference[modality]['grid']
    quantiles = reference[modality]['values']
    mapped = flat.copy()
    sub = flat[mask]
    for dim in range(flat.shape[1]):
        column = sub[:, dim]
        ranks = column.argsort().argsort().astype(np.float64) / max(len(column) - 1, 1)
        mapped[mask, dim] = np.interp(ranks, grid, quantiles[:, dim])
    normalized = (mapped - stats[modality]['mean']) / stats[modality]['std']
    normalized[~mask] = 0.0
    return normalized.reshape(data.shape).astype(np.float32)

def normalize(array: np.ndarray, modality: str, stats: dict) -> np.ndarray:
    data = np.asarray(array, dtype=np.float64)
    if modality == 'audio':
        data = _scale_audio_columns(data)
    mean = stats[modality]['mean']
    std = stats[modality]['std']
    return ((data - mean) / std).astype(np.float32)

def valid_mask(array: np.ndarray) -> np.ndarray:
    energy = np.abs(np.asarray(array, dtype=np.float64)).reshape(array.shape[0], array.shape[1], -1).sum(axis=2)
    return (energy > 0).astype(np.float32)

def prepare_split(aligned: dict, stats: dict, split: str) -> dict:
    out = {}
    for modality in MODALITIES:
        raw = np.asarray(aligned[f'{split}_{modality}'])
        out[modality] = normalize(raw, modality, stats)
        out[f'{modality}_mask'] = valid_mask(raw)
    out['label_cls'] = np.asarray(aligned[f'{split}_cls'], dtype=np.int64)
    out['label_reg'] = np.asarray(aligned[f'{split}_reg'], dtype=np.float32)
    out['ids'] = np.asarray(aligned[f'{split}_ids'])
    return out

def load_a3() -> dict:
    folder = RAW / '附件3-模态缺失特征样本' / '对齐版本'
    text, audio, vision = ([], [], [])
    names = []
    for path in sorted(folder.glob('*.pkl')):
        with open(path, 'rb') as handle:
            part = pickle.load(handle, encoding='latin1')['test']
        text.append(np.asarray(part['text_bert'], dtype=np.float32)[0].T)
        audio.append(np.asarray(part['audio'], dtype=np.float32)[0])
        vision.append(np.asarray(part['vision'], dtype=np.float32)[0])
        names.append(path.stem)
    return {'text_bert': np.stack(text), 'audio': np.stack(audio), 'vision': np.stack(vision), 'names': np.asarray(names)}

def load_a4() -> dict:
    data = np.load(DATA / 'a4_aligned.npz', allow_pickle=True)
    return {'text': data['text'], 'audio': data['audio'], 'vision': data['vision'], 'text_bert': data['text_bert'], 'ids': data['ids']}

def a3_missing_plan() -> list[dict]:
    import json
    import pandas as pd
    frame = pd.read_csv(DATA / 'a3_missing_mask.csv')
    plan = []
    for _, row in frame.iterrows():
        item = {'sample': row['sample']}
        for modality in MODALITIES:
            segments = json.loads(row[f'{modality}_missing_segments'])
            item[modality] = [tuple(seg) for seg in segments]
        plan.append(item)
    return plan

def apply_segments(array: np.ndarray, segments: list[tuple[int, int]]) -> np.ndarray:
    out = np.array(array, copy=True)
    for start, end in segments:
        out[start:end + 1] = 0.0
    return out

def sample_missing_segments(rng: np.random.Generator, seq_len: int, ratio: float, max_segments: int=3, min_len: int=1) -> list[tuple[int, int]]:
    target = int(round(ratio * seq_len))
    if target <= 0:
        return []
    segments: list[tuple[int, int]] = []
    remaining = target
    attempts = 0
    while remaining > 0 and attempts < 200:
        attempts += 1
        length = int(rng.integers(min_len, max(min_len, remaining) + 1))
        length = min(length, remaining)
        start = int(rng.integers(0, max(1, seq_len - length + 1)))
        end = start + length - 1
        overlap = sum((max(0, min(end, e) - max(start, s) + 1) for s, e in segments))
        if overlap > 0:
            continue
        segments.append((start, end))
        remaining -= length
        if len(segments) >= max_segments and remaining > 0:
            segments.append((seq_len - remaining, seq_len - 1))
            remaining = 0
    return segments

def corrupt(array: np.ndarray, segments: list[tuple[int, int]]) -> np.ndarray:
    return apply_segments(array, segments)

def metrics_classification(pred: np.ndarray, target: np.ndarray) -> dict:
    pred = np.asarray(pred).astype(int)
    target = np.asarray(target).astype(int)
    accuracy = float((pred == target).mean())
    labels = sorted(set(target.tolist()) | set(pred.tolist()))
    f1_values = []
    for label in labels:
        tp = float(((pred == label) & (target == label)).sum())
        fp = float(((pred == label) & (target != label)).sum())
        fn = float(((pred != label) & (target == label)).sum())
        precision = tp / (tp + fp) if tp + fp > 0 else 0.0
        recall = tp / (tp + fn) if tp + fn > 0 else 0.0
        f1_values.append(2 * precision * recall / (precision + recall) if precision + recall > 0 else 0.0)
    return {'accuracy': accuracy, 'macro_f1': float(np.mean(f1_values)) if f1_values else 0.0, 'weighted_f1': float(np.average(f1_values, weights=[int((target == label).sum()) for label in labels])) if labels and int((target == labels[0]).sum()) >= 0 else 0.0}

def metrics_regression(pred: np.ndarray, target: np.ndarray) -> dict:
    pred = np.asarray(pred, dtype=np.float64)
    target = np.asarray(target, dtype=np.float64)
    mae = float(np.abs(pred - target).mean())
    if pred.std() < EPS or target.std() < EPS:
        pearson = 0.0
    else:
        pearson = float(np.corrcoef(pred, target)[0, 1])
    return {'mae': mae, 'pearson': pearson, 'rmse': float(np.sqrt(((pred - target) ** 2).mean()))}
