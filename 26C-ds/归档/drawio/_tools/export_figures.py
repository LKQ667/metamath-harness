# -*- coding: utf-8 -*-
"""按固定产物契约导出 12 张图的 2× PNG / SVG / PDF。"""
import os
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
SKILL = Path(os.environ.get('MATH_PAPER_HUAWEI_SKILL', 'skills/math-paper-huawei')).resolve()
PIPELINE = SKILL / 'scripts' / 'drawing' / 'drawio_pipeline.py'
HAND = Path(__file__).resolve().parents[2] / '手绘图'

names = [p.stem for p in sorted(HAND.glob('*.drawio'))]
out = []
for name in names:
    src = HAND / f'{name}.drawio'
    proc = subprocess.run([sys.executable, str(PIPELINE), 'export', str(src),
                           '--output-dir', str(HAND)],
                          text=True, encoding='utf-8', errors='replace', capture_output=True)
    sizes = {}
    for ext in ('png', 'svg', 'pdf'):
        f = HAND / f'{name}.{ext}'
        sizes[ext] = f.stat().st_size if f.exists() else 0
    rec = {'name': name, 'exit': proc.returncode, 'sizes': sizes}
    if proc.returncode != 0:
        rec['stderr'] = proc.stderr[-800:]
    out.append(rec)
    print(json.dumps(rec, ensure_ascii=False))

(HAND / '_tools' / 'export_summary.json').write_text(
    json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
bad = [r for r in out if r['exit'] != 0 or min(r['sizes'].values()) == 0]
print(f'\nEXPORT FAILURES: {len(bad)} / {len(out)}')
raise SystemExit(1 if bad else 0)
