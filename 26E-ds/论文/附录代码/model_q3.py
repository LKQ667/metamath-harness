from __future__ import annotations
import sys
from pathlib import Path
import torch
import torch.nn as nn
PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / 'scripts'))
DEVICE = torch.device('cpu')

class InterpretableFusion(nn.Module):

    def __init__(self, hidden: int=192, n_modalities: int=3, dropout: float=0.15):
        super().__init__()
        self.hidden = hidden
        self.n_modalities = n_modalities
        self.project = nn.ModuleList([nn.Linear(hidden, hidden) for _ in range(n_modalities)])
        self.modality_query = nn.Linear(hidden, 1)
        self.position_query = nn.Linear(hidden, 1)
        self.compat = nn.ModuleList([nn.Linear(hidden, hidden) for _ in range(n_modalities)])
        self.fuse = nn.Sequential(nn.Linear(hidden * n_modalities, hidden), nn.GELU(), nn.Dropout(dropout), nn.Linear(hidden, hidden))
        self.norm = nn.LayerNorm(hidden)
        self.drop = nn.Dropout(dropout)
        self.cls = nn.Linear(hidden, 3)
        self.reg = nn.Linear(hidden, 1)

    def forward(self, sequences: list[torch.Tensor], masks: list[torch.Tensor]) -> dict:
        batch, steps, _ = sequences[0].shape
        projected = [self.project[i](sequence) for i, sequence in enumerate(sequences)]
        pooled = []
        for index, item in enumerate(projected):
            mask = masks[index]
            score = self.modality_query(item).squeeze(-1).masked_fill(mask <= 0, -1000000000.0)
            weight = torch.softmax(score, dim=1) * mask
            weight = weight / weight.sum(dim=1, keepdim=True).clamp_min(1e-06)
            pooled.append((item * weight.unsqueeze(-1)).sum(dim=1))
        stacked = torch.stack(pooled, dim=1)
        logits_modality = self.modality_query(stacked).squeeze(-1)
        alpha = torch.softmax(logits_modality, dim=1)
        weight_sum = torch.stack(masks, dim=2).sum(dim=2)
        valid = weight_sum > 0
        compat = torch.stack([torch.tanh(self.compat[i](projected[i])) for i in range(self.n_modalities)], dim=2)
        fused = self.fuse(compat.flatten(2))
        fused = self.norm(fused)
        position_score = self.position_query(fused).squeeze(-1)
        position_score = position_score.masked_fill(~valid, -1000000000.0)
        beta = torch.softmax(position_score, dim=1) * valid.float()
        beta = beta / beta.sum(dim=1, keepdim=True).clamp_min(1e-06)
        pooled_final = (fused * beta.unsqueeze(-1)).sum(dim=1)
        pooled_final = self.drop(pooled_final)
        contribution = torch.zeros(batch, self.n_modalities, steps, device=sequences[0].device)
        for index in range(self.n_modalities):
            mask = masks[index]
            score = self.modality_query(projected[index]).squeeze(-1).masked_fill(mask <= 0, -1000000000.0)
            weight = torch.softmax(score, dim=1) * mask
            weight = weight / weight.sum(dim=1, keepdim=True).clamp_min(1e-06)
            contribution[:, index, :] = alpha[:, index].unsqueeze(1) * weight * mask
        return {'logits': self.cls(pooled_final), 'regression': self.reg(pooled_final).squeeze(-1), 'pooled': pooled_final, 'modality_alpha': alpha, 'position_beta': beta, 'position_contribution': contribution, 'fused': fused}

def build_interpretable(hidden: int=192, dropout: float=0.15) -> InterpretableFusion:
    return InterpretableFusion(hidden=hidden, dropout=dropout)
