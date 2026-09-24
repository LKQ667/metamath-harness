from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "scripts"))

import mm_data as md

OUT = PROJECT / "Q2"
CACHE = OUT / "cache"
SEED = 20260924
DEVICE = torch.device("cpu")


class ModalityEncoder(nn.Module):
    """单模态时序编码器：线性投影 + 双向门控循环单元 + 注意力池化。"""

    def __init__(self, input_dim: int, hidden: int = 96, latent: int = 64, dropout: float = 0.15):
        super().__init__()
        self.proj = nn.Linear(input_dim, hidden)
        self.norm = nn.LayerNorm(hidden)
        self.act = nn.GELU()
        self.gru = nn.GRU(hidden, hidden, num_layers=1, batch_first=True, bidirectional=True)
        self.drop = nn.Dropout(dropout)
        self.query = nn.Linear(2 * hidden, 1)
        self.out = nn.Linear(2 * hidden, latent)

    def forward(self, x: torch.Tensor, mask: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        h = self.act(self.norm(self.proj(x)))
        h = self.drop(h)
        h, _ = self.gru(h)
        h = self.drop(h)
        score = self.query(h).squeeze(-1)
        score = score.masked_fill(mask <= 0, -1e9)
        weight = torch.softmax(score, dim=1) * mask
        weight = weight / weight.sum(dim=1, keepdim=True).clamp_min(1e-6)
        pooled = (h * weight.unsqueeze(-1)).sum(dim=1)
        return self.out(pooled), h


class SingleHead(nn.Module):
    def __init__(self, input_dim: int, hidden: int = 96, latent: int = 64, dropout: float = 0.15):
        super().__init__()
        self.encoder = ModalityEncoder(input_dim, hidden, latent, dropout)
        self.cls = nn.Linear(latent, 3)
        self.reg = nn.Linear(latent, 1)

    def forward(self, x: torch.Tensor, mask: torch.Tensor):
        pooled, _ = self.encoder(x, mask)
        return self.cls(pooled), self.reg(pooled).squeeze(-1), pooled


def make_tensor(array: np.ndarray, mask: np.ndarray, index: np.ndarray) -> tuple[torch.Tensor, torch.Tensor]:
    x = torch.from_numpy(np.asarray(array)[index]).float()
    m = torch.from_numpy(np.asarray(mask)[index]).float()
    return x, m


def class_weights(labels: np.ndarray) -> torch.Tensor:
    counts = np.bincount(labels, minlength=3).astype(np.float64)
    weights = counts.sum() / (3.0 * np.maximum(counts, 1.0))
    return torch.tensor(weights, dtype=torch.float32)


def train_single(modality: str, prepared: dict, epochs: int, batch: int, lr: float,
                 seed: int, verbose: bool = True) -> dict:
    torch.manual_seed(seed)
    np.random.seed(seed)
    model = SingleHead(md.DIMS[modality]).to(DEVICE)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    ce = nn.CrossEntropyLoss(weight=class_weights(prepared["train"]["label_cls"]))
    huber = nn.SmoothL1Loss(beta=0.5)
    n_train = len(prepared["train"]["label_cls"])
    history = []
    for epoch in range(1, epochs + 1):
        model.train()
        order = np.random.permutation(n_train)
        total = 0.0
        for start in range(0, n_train, batch):
            index = order[start:start + batch]
            x, m = make_tensor(prepared["train"][modality], prepared["train"][f"{modality}_mask"], index)
            y_cls = torch.from_numpy(prepared["train"]["label_cls"][index]).long()
            y_reg = torch.from_numpy(prepared["train"]["label_reg"][index]).float()
            logits, reg, _ = model(x, m)
            loss = ce(logits, y_cls) + huber(reg, y_reg)
            optimizer.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            optimizer.step()
            total += float(loss.item()) * len(index)
        history.append({"epoch": epoch, "loss": total / n_train})
        if verbose and epoch % 5 == 0:
            print(f"  [{modality}] epoch {epoch} loss {history[-1]['loss']:.4f}", flush=True)

    model.eval()
    result = {"modality": modality, "history": history}
    with torch.no_grad():
        for split in ("valid", "test"):
            index = np.arange(len(prepared[split]["label_cls"]))
            x, m = make_tensor(prepared[split][modality], prepared[split][f"{modality}_mask"], index)
            logits, reg, _ = model(x, m)
            pred_cls = logits.argmax(dim=1).numpy()
            result[split] = {
                **md.metrics_classification(pred_cls, prepared[split]["label_cls"]),
                **md.metrics_regression(reg.numpy(), prepared[split]["label_reg"]),
            }
    torch.save(model.state_dict(), CACHE / f"encoder_{modality}.pt")
    return result


def encode_all(model: SingleHead, prepared: dict, modality: str, split: str) -> tuple[np.ndarray, np.ndarray]:
    model.eval()
    index = np.arange(len(prepared[split]["label_cls"]))
    x, m = make_tensor(prepared[split][modality], prepared[split][f"{modality}_mask"], index)
    with torch.no_grad():
        pooled, sequence = model.encoder(x, m)
    return sequence.numpy().astype(np.float32), pooled.numpy().astype(np.float32)


def main() -> int:
    parser = argparse.ArgumentParser(description="训练并冻结单模态时序编码器，缓存编码序列")
    parser.add_argument("--epochs", type=int, default=24)
    parser.add_argument("--batch", type=int, default=64)
    parser.add_argument("--lr", type=float, default=2e-3)
    args = parser.parse_args()

    CACHE.mkdir(parents=True, exist_ok=True)
    aligned = md.load_aligned()
    stats = md.normalization_stats(aligned)
    prepared = {split: md.prepare_split(aligned, stats, split) for split in md.SPLITS}
    np.savez_compressed(CACHE / "norm_stats.npz",
                        **{f"{m}_{k}": v for m, item in stats.items() for k, v in item.items()})

    results = []
    for modality in md.MODALITIES:
        print(f"training encoder for {modality}", flush=True)
        started = time.time()
        outcome = train_single(modality, prepared, args.epochs, args.batch, args.lr, SEED)
        outcome["seconds"] = round(time.time() - started, 1)
        results.append(outcome)

    cache = {}
    for modality in md.MODALITIES:
        model = SingleHead(md.DIMS[modality]).to(DEVICE)
        model.load_state_dict(torch.load(CACHE / f"encoder_{modality}.pt", map_location=DEVICE))
        for split in md.SPLITS:
            sequence, pooled = encode_all(model, prepared, modality, split)
            cache[f"{split}_{modality}_seq"] = sequence
            cache[f"{split}_{modality}_pool"] = pooled
            cache[f"{split}_{modality}_mask"] = prepared[split][f"{modality}_mask"].astype(np.float32)
    for split in md.SPLITS:
        cache[f"{split}_label_cls"] = prepared[split]["label_cls"]
        cache[f"{split}_label_reg"] = prepared[split]["label_reg"]
    np.savez_compressed(CACHE / "encoded_sequences.npz", **cache)

    (OUT / "encoder_report.json").write_text(
        json.dumps({"results": results, "config": vars(args), "seed": SEED}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({"ok": True, "modalities": [item["modality"] for item in results],
                      "valid": {item["modality"]: item["valid"] for item in results}},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
