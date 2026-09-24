from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import torch
import torch.nn as nn
PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / 'scripts'))
import mm_data as md
DEVICE = torch.device('cpu')

def masked_softmax(score: torch.Tensor, mask: torch.Tensor, dim: int) -> torch.Tensor:
    score = score.masked_fill(mask <= 0, -1000000000.0)
    weight = torch.softmax(score, dim=dim)
    return weight * mask

class ReliabilityGate(nn.Module):

    def __init__(self, hidden: int, n_modalities: int=3, embed: int=8):
        super().__init__()
        self.embedding = nn.Embedding(n_modalities, embed)
        self.net = nn.Sequential(nn.Linear(hidden + 1 + embed, int(hidden / 2)), nn.GELU(), nn.Linear(int(hidden / 2), 1))

    def forward(self, sequence: torch.Tensor, mask: torch.Tensor, modality_index: int) -> torch.Tensor:
        batch, steps, hidden = sequence.shape
        embed = self.embedding(torch.full((batch, steps), modality_index, dtype=torch.long, device=sequence.device))
        features = torch.cat([sequence, mask.unsqueeze(-1), embed], dim=-1)
        logit = self.net(features).squeeze(-1)
        return torch.sigmoid(logit)

class RobustFusion(nn.Module):

    def __init__(self, hidden: int=192, n_modalities: int=3, dropout: float=0.15, use_gate: bool=True, use_attention: bool=True):
        super().__init__()
        self.hidden = hidden
        self.n_modalities = n_modalities
        self.use_gate = use_gate
        self.use_attention = use_attention
        self.project = nn.ModuleList([nn.Linear(hidden, hidden) for _ in range(n_modalities)])
        self.gate = ReliabilityGate(hidden, n_modalities) if use_gate else None
        self.attention = nn.MultiheadAttention(hidden, num_heads=4, dropout=dropout, batch_first=True) if use_attention else None
        self.temporal = nn.Sequential(nn.Linear(hidden, hidden), nn.GELU(), nn.Dropout(dropout), nn.Linear(hidden, hidden))
        self.summary = nn.Sequential(nn.Linear(hidden * n_modalities * 2 + n_modalities, hidden), nn.GELU(), nn.Dropout(dropout), nn.Linear(hidden, hidden))
        self.blend = nn.Parameter(torch.tensor(0.0))
        self.pool_query = nn.Linear(hidden, 1)
        self.norm = nn.LayerNorm(hidden)
        self.drop = nn.Dropout(dropout)
        self.cls = nn.Linear(hidden, 3)
        self.reg = nn.Linear(hidden, 1)
        self.modality_scale = nn.Parameter(torch.ones(n_modalities))

    def forward(self, sequences: list[torch.Tensor], masks: list[torch.Tensor]) -> dict:
        batch, steps, _ = sequences[0].shape
        fused = torch.zeros(batch, steps, self.hidden, device=sequences[0].device)
        weight_sum = torch.zeros(batch, steps, 1, device=sequences[0].device)
        modality_mass = []
        gate_values = []
        summaries = []
        for index, (sequence, mask) in enumerate(zip(sequences, masks)):
            projected = self.project[index](sequence)
            if self.gate is not None:
                reliability = self.gate(sequence, mask, index)
            else:
                reliability = mask
            effective = reliability * mask
            contribution = effective.unsqueeze(-1) * projected * self.modality_scale[index]
            fused = fused + contribution
            weight_sum = weight_sum + effective.unsqueeze(-1)
            modality_mass.append(effective.sum(dim=1))
            gate_values.append(effective)
            ratio = mask.mean(dim=1, keepdim=True)
            summaries.append(projected.mean(dim=1) * ratio)
            summaries.append(projected.amax(dim=1) * ratio)
            summaries.append(ratio)
        fused = fused / weight_sum.clamp_min(1e-06)
        if self.attention is not None:
            key_padding = weight_sum.squeeze(-1) <= 1e-06
            attended, attention_map = self.attention(fused, fused, fused, key_padding_mask=key_padding)
            fused = self.norm(fused + self.drop(attended))
        else:
            attention_map = None
            fused = self.norm(fused)
        fused = fused + self.temporal(fused)
        score = self.pool_query(fused).squeeze(-1)
        valid = weight_sum.squeeze(-1) > 1e-06
        score = score.masked_fill(~valid, -1000000000.0)
        weight = torch.softmax(score, dim=1) * valid.float()
        weight = weight / weight.sum(dim=1, keepdim=True).clamp_min(1e-06)
        pooled = (fused * weight.unsqueeze(-1)).sum(dim=1)
        summary_vector = self.summary(torch.cat(summaries, dim=-1))
        pooled = pooled + torch.tanh(self.blend) * summary_vector
        pooled = self.drop(pooled)
        mass = torch.stack(modality_mass, dim=1)
        mass = mass / mass.sum(dim=1, keepdim=True).clamp_min(1e-06)
        return {'logits': self.cls(pooled), 'regression': self.reg(pooled).squeeze(-1), 'pooled': pooled, 'temporal_weight': weight, 'modality_mass': mass, 'gate_values': gate_values, 'attention_map': attention_map, 'fused': fused}

class MeanFusion(nn.Module):

    def __init__(self, hidden: int=192, dropout: float=0.15):
        super().__init__()
        self.temporal = nn.Sequential(nn.Linear(hidden, hidden), nn.GELU(), nn.Dropout(dropout))
        self.pool_query = nn.Linear(hidden, 1)
        self.norm = nn.LayerNorm(hidden)
        self.cls = nn.Linear(hidden, 3)
        self.reg = nn.Linear(hidden, 1)
        self.drop = nn.Dropout(dropout)

    def forward(self, sequences: list[torch.Tensor], masks: list[torch.Tensor]) -> dict:
        stacked = torch.stack(sequences, dim=2)
        stacked_mask = torch.stack(masks, dim=2)
        mass = stacked_mask.sum(dim=2, keepdim=True)
        fused = (stacked * stacked_mask.unsqueeze(-1)).sum(dim=2) / mass.clamp_min(1e-06)
        fused = self.norm(fused + self.drop(self.temporal(fused)))
        score = self.pool_query(fused).squeeze(-1)
        valid = mass.squeeze(-1) > 1e-06
        score = score.masked_fill(~valid, -1000000000.0)
        weight = torch.softmax(score, dim=1) * valid.float()
        weight = weight / weight.sum(dim=1, keepdim=True).clamp_min(1e-06)
        pooled = (fused * weight.unsqueeze(-1)).sum(dim=1)
        modality_mass = stacked_mask.sum(dim=1)
        modality_mass = modality_mass / modality_mass.sum(dim=1, keepdim=True).clamp_min(1e-06)
        return {'logits': self.cls(pooled), 'regression': self.reg(pooled).squeeze(-1), 'pooled': pooled, 'temporal_weight': weight, 'modality_mass': modality_mass, 'gate_values': [stacked_mask[:, :, i] for i in range(stacked_mask.shape[2])], 'attention_map': None, 'fused': fused}

class TensorFusion(nn.Module):

    def __init__(self, hidden: int=192, dropout: float=0.15):
        super().__init__()
        self.hidden = hidden
        self.compress = nn.Linear(hidden, 8)
        self.proj = nn.Linear(3 * 8 + 3 * 64 + 512, hidden)
        self.temporal = nn.Sequential(nn.Linear(hidden, hidden), nn.GELU(), nn.Dropout(dropout))
        self.pool_query = nn.Linear(hidden, 1)
        self.norm = nn.LayerNorm(hidden)
        self.cls = nn.Linear(hidden, 3)
        self.reg = nn.Linear(hidden, 1)
        self.drop = nn.Dropout(dropout)

    def forward(self, sequences: list[torch.Tensor], masks: list[torch.Tensor]) -> dict:
        a, b, c = [torch.tanh(self.compress(item)) for item in sequences]
        outer_ab = torch.einsum('bth,btk->bthk', a, b).flatten(2)
        outer_ac = torch.einsum('bth,btk->bthk', a, c).flatten(2)
        outer_bc = torch.einsum('bth,btk->bthk', b, c).flatten(2)
        triple = torch.einsum('bth,btk,btm->bthkm', a, b, c).flatten(2)
        fused = self.proj(torch.cat([a, b, c, outer_ab, outer_ac, outer_bc, triple], dim=-1))
        valid = torch.stack(masks, dim=2).sum(dim=2) > 0
        fused = self.norm(fused + self.drop(self.temporal(fused)))
        score = self.pool_query(fused).squeeze(-1).masked_fill(~valid, -1000000000.0)
        weight = torch.softmax(score, dim=1) * valid.float()
        weight = weight / weight.sum(dim=1, keepdim=True).clamp_min(1e-06)
        pooled = (fused * weight.unsqueeze(-1)).sum(dim=1)
        stacked_mask = torch.stack(masks, dim=2)
        modality_mass = stacked_mask.sum(dim=1)
        modality_mass = modality_mass / modality_mass.sum(dim=1, keepdim=True).clamp_min(1e-06)
        return {'logits': self.cls(pooled), 'regression': self.reg(pooled).squeeze(-1), 'pooled': pooled, 'temporal_weight': weight, 'modality_mass': modality_mass, 'gate_values': [stacked_mask[:, :, i] for i in range(stacked_mask.shape[2])], 'attention_map': None, 'fused': fused}

class LowRankFusion(nn.Module):

    def __init__(self, hidden: int=192, rank: int=8, dropout: float=0.15):
        super().__init__()
        self.factors = nn.Parameter(torch.randn(3, hidden, rank) * 0.02)
        self.bias = nn.Parameter(torch.zeros(hidden))
        self.out = nn.Linear(rank, hidden)
        self.temporal = nn.Sequential(nn.Linear(hidden, hidden), nn.GELU(), nn.Dropout(dropout))
        self.pool_query = nn.Linear(hidden, 1)
        self.norm = nn.LayerNorm(hidden)
        self.cls = nn.Linear(hidden, 3)
        self.reg = nn.Linear(hidden, 1)
        self.drop = nn.Dropout(dropout)

    def forward(self, sequences: list[torch.Tensor], masks: list[torch.Tensor]) -> dict:
        projected = [torch.einsum('bth,hr->btr', sequence, factor) for sequence, factor in zip(sequences, self.factors)]
        stacked_mask = torch.stack(masks, dim=2)
        mass = stacked_mask.sum(dim=1)
        gate = mass / mass.sum(dim=1, keepdim=True).clamp_min(1e-06)
        fused = torch.zeros_like(projected[0])
        for index, item in enumerate(projected):
            fused = fused + item * gate[:, index].reshape(-1, 1, 1)
        fused = self.out(fused)
        valid = stacked_mask.sum(dim=2) > 0
        fused = self.norm(fused + self.drop(self.temporal(fused)))
        score = self.pool_query(fused).squeeze(-1).masked_fill(~valid, -1000000000.0)
        pool_weight = torch.softmax(score, dim=1) * valid.float()
        pool_weight = pool_weight / pool_weight.sum(dim=1, keepdim=True).clamp_min(1e-06)
        pooled = (fused * pool_weight.unsqueeze(-1)).sum(dim=1)
        modality_mass = stacked_mask.sum(dim=1)
        modality_mass = modality_mass / modality_mass.sum(dim=1, keepdim=True).clamp_min(1e-06)
        return {'logits': self.cls(pooled), 'regression': self.reg(pooled).squeeze(-1), 'pooled': pooled, 'temporal_weight': pool_weight, 'modality_mass': modality_mass, 'gate_values': [stacked_mask[:, :, i] for i in range(stacked_mask.shape[2])], 'attention_map': None, 'fused': fused}

class SingleModalityFusion(nn.Module):

    def __init__(self, hidden: int=192, keep: int=0, dropout: float=0.15):
        super().__init__()
        self.keep = keep
        self.temporal = nn.Sequential(nn.Linear(hidden, hidden), nn.GELU(), nn.Dropout(dropout))
        self.pool_query = nn.Linear(hidden, 1)
        self.norm = nn.LayerNorm(hidden)
        self.cls = nn.Linear(hidden, 3)
        self.reg = nn.Linear(hidden, 1)
        self.drop = nn.Dropout(dropout)

    def forward(self, sequences: list[torch.Tensor], masks: list[torch.Tensor]) -> dict:
        fused = sequences[self.keep]
        valid = masks[self.keep] > 0
        fused = self.norm(fused + self.drop(self.temporal(fused)))
        score = self.pool_query(fused).squeeze(-1).masked_fill(~valid, -1000000000.0)
        weight = torch.softmax(score, dim=1) * valid.float()
        weight = weight / weight.sum(dim=1, keepdim=True).clamp_min(1e-06)
        pooled = (fused * weight.unsqueeze(-1)).sum(dim=1)
        modality_mass = torch.zeros(sequences[0].shape[0], 3, device=sequences[0].device)
        modality_mass[:, self.keep] = 1.0
        gate_values = [torch.zeros_like(masks[0]) for _ in sequences]
        gate_values[self.keep] = masks[self.keep]
        return {'logits': self.cls(pooled), 'regression': self.reg(pooled).squeeze(-1), 'pooled': pooled, 'temporal_weight': weight, 'modality_mass': modality_mass, 'gate_values': gate_values, 'attention_map': None, 'fused': fused}

def load_encoder(modality: str, cache_dir, hidden: int=96, latent: int=64):
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Q2'))
    from train_encoders import SingleHead
    model = SingleHead(md.DIMS[modality], hidden, latent)
    state = torch.load(Path(cache_dir) / f'encoder_{modality}.pt', map_location=DEVICE)
    model.load_state_dict(state)
    model.eval()
    return model

def encode_sequence(encoder, array: np.ndarray) -> np.ndarray:
    x = torch.from_numpy(np.asarray(array)).float()
    mask = torch.from_numpy(md.valid_mask(array)).float()
    with torch.no_grad():
        _, sequence = encoder.encoder(x, mask)
    return sequence.numpy().astype(np.float32)

def build_model(name: str, hidden: int=192) -> nn.Module:
    if name == 'robust_full':
        return RobustFusion(hidden, use_gate=True, use_attention=True)
    if name == 'robust_no_gate':
        return RobustFusion(hidden, use_gate=False, use_attention=True)
    if name == 'robust_no_attention':
        return RobustFusion(hidden, use_gate=True, use_attention=False)
    if name == 'mean_fusion':
        return MeanFusion(hidden)
    if name == 'tensor_fusion':
        return TensorFusion(hidden)
    if name == 'lowrank_fusion':
        return LowRankFusion(hidden)
    if name.startswith('single_'):
        return SingleModalityFusion(hidden, keep=md.MODALITIES.index(name.split('_', 1)[1]))
    raise ValueError(f'unknown model: {name}')
MODEL_NAMES = ('robust_full', 'robust_no_gate', 'robust_no_attention', 'mean_fusion', 'tensor_fusion', 'lowrank_fusion', 'single_text', 'single_audio', 'single_vision')
