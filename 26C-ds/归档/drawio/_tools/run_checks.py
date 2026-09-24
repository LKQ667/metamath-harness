# -*- coding: utf-8 -*-
"""运行四条自检命令并把结果汇总成报告数据。"""
import os
import json, struct, subprocess, sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
K = Path(os.environ.get('MATH_PAPER_HUAWEI_CHECKS', 'scripts/checks')).resolve()
P = Path(__file__).resolve().parents[2]
R = P / '检查结果'
HAND = P / '手绘图'

JOBS = [
    ('check_figures_manifest', ['check_figures_manifest.py', '--project', str(P)],
     ['--output', str(R / 'check_figures_manifest.json')]),
    ('check_flowchart_required', ['check_flowchart_required.py', '--project', str(P)],
     ['--output', str(R / 'check_flowchart_required.json')]),
    ('check_drawing_contract', ['check_drawing_contract.py', '--project', str(P)],
     ['--output', str(R / 'check_drawing_contract.json')]),
    ('check_roadmap_quality_notes', ['check_roadmap_quality_notes.py', '--project', str(P)],
     ['--output', str(R / 'check_roadmap_quality_notes.json')]),
]

checks = []
for name, base, extra in JOBS:
    proc = subprocess.run([sys.executable, str(K / base[0]), *base[1:], *extra],
                          text=True, encoding='utf-8', errors='replace', capture_output=True)
    rec = {'check': name, 'exit': proc.returncode}
    try:
        rep = json.loads(proc.stdout)
        rec['ok'] = rep['ok']
        rec['error_count'] = len(rep['errors'])
        rec['errors'] = rep['errors']
    except Exception:
        rec['ok'] = None
        rec['raw'] = (proc.stdout or proc.stderr)[:800]
    checks.append(rec)

# 产物清单
manifest = json.loads((P / 'figures' / 'manifest.json').read_text(encoding='utf-8'))
arts = []
for it in manifest['items']:
    name = it['name']
    row = {'name': name, 'template_id': it['template_id']}
    for ext in ('drawio', 'svg', 'pdf', 'png'):
        f = HAND / f'{name}.{ext}'
        row[ext] = f.stat().st_size if f.exists() else 0
    png = HAND / f'{name}.png'
    if png.exists():
        d = png.read_bytes()
        w, h = struct.unpack('>II', d[16:24])
        row['png_wh'] = f'{w}x{h}'
        row['ratio'] = round(w / h, 3)
    arts.append(row)

out = {'checks': checks, 'artifacts': arts}
(HAND / '_tools' / 'final_report_data.json').write_text(
    json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')

for c in checks:
    print(f"{c['check']:34s} exit={c['exit']} ok={c.get('ok')} errors={c.get('error_count')}")
print()
print(f"{'name':32s} {'template_id':22s} {'PNG':>12s} {'ratio':>6s} {'png':>8s} {'pdf':>7s} {'svg':>8s}")
for a in arts:
    print(f"{a['name']:32s} {a['template_id']:22s} {a.get('png_wh',''):>12s} "
          f"{a.get('ratio',0):6.2f} {a['png']:8d} {a['pdf']:7d} {a['svg']:8d}")
