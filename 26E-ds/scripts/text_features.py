from __future__ import annotations

import hashlib
import re

import numpy as np

TEXT_DIM = 768
SEQ_LEN = 50
HASH_PERSON = b"mosei2026"
TOKEN_RE = re.compile(r"[a-z0-9']+")


def tokens_of(text: str) -> list[str]:
    return TOKEN_RE.findall(str(text).lower().replace("’", "'"))


def hash_index(term: str, buckets: int = TEXT_DIM) -> int:
    digest = hashlib.blake2b(term.encode("utf-8"), digest_size=8, person=HASH_PERSON).digest()
    return int.from_bytes(digest, "big") % buckets


def text_features(text: str, seq_len: int = SEQ_LEN) -> np.ndarray:
    """与问题一完全一致的哈希词袋文本表示：位置 k 覆盖词元区间 [floor(kT/L), floor((k+1)T/L))。"""
    tokens = tokens_of(text)
    features = np.zeros((seq_len, TEXT_DIM), dtype=np.float32)
    if not tokens:
        return features
    total = len(tokens)
    for index in range(seq_len):
        start = int(np.floor(index * total / seq_len))
        stop = int(np.floor((index + 1) * total / seq_len))
        if stop <= start:
            stop = min(start + 1, total)
        window = tokens[start:stop]
        if not window:
            continue
        vector = np.zeros(TEXT_DIM, dtype=np.float32)
        for position, token in enumerate(window):
            vector[hash_index(token)] += 1.0
            if position + 1 < len(window):
                vector[hash_index(token + "_" + window[position + 1])] += 0.5
        norm = float(np.linalg.norm(vector))
        if norm > 0:
            vector = vector / norm
        features[index] = vector
    return features
