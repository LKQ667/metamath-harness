# -*- coding: utf-8 -*-
"""交付前最终自检：manifest 字段完整性 + 禁止目录未被改动。"""
import json, subprocess, sys, time
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
P = Path(__file__).resolve().parents[2]
HAND = P / '手绘图'
REQ = ('generator', 'template_id', 'source', 'exports', 'prompt_source', 'paper_ready',
       'export_status', 'needs_visual_review', 'qa')
QA_REQ = ('xml_ok', 'unique_ids_ok', 'endpoints_ok', 'cn_font_ok', 'orthogonal_ok',
          'no_overlap_ok', 'content_ok', 'crop_ok', 'text_fit_ok', 'grayscale_ok',
          'single_column_ok', 'double_column_ok', 'paper_insert_ok',
          'static_check_ok', 'cli_export_ok', 'cn_text_ok', 'layout_ok',
          'edge_routing_ok', 'node_overlap_ok')

m = json.loads((P / 'figures' / 'manifest.json').read_text(encoding='utf-8'))
print('顶层字段:', list(m.keys()))
print('drawing_mode:', m['drawing_mode'], '| locked:', m['drawing_mode_locked'],
      '| confirmed:', m['drawing_mode_confirmed'], '| source:', m['drawing_mode_source'])
print('条目数:', len(m['items']))
bad = []
for it in m['items']:
    for k in REQ:
        if k not in it:
            bad.append(f"{it.get('name')}: 缺字段 {k}")
    for k in QA_REQ:
        if it['qa'].get(k) is not True:
            bad.append(f"{it.get('name')}: qa.{k} != true")
    if it['generator'] != 'drawio':
        bad.append(f"{it.get('name')}: generator != drawio")
    if not it['source'].startswith('手绘图/') or not it['source'].endswith('.drawio'):
        bad.append(f"{it.get('name')}: source 不合规 {it['source']}")
    if it['export_scale'] != 2 or it['export_status'] != 'cli_exported':
        bad.append(f"{it.get('name')}: export_scale/export_status 不合规")
    if it['chart_family'] != 'flowchart':
        bad.append(f"{it.get('name')}: chart_family != flowchart")
    for rel in [it['source'], it['prompt_source'], *it['exports']]:
        if not (P / rel).exists():
            bad.append(f"{it.get('name')}: 文件不存在 {rel}")
print('manifest 问题:', len(bad))
for b in bad:
    print('  -', b)

# 禁止目录改动核查（只看本会话时间窗内的 mtime）
cutoff = time.time() - 4 * 3600
for d in ('数据预处理', 'Q1', 'Q2', 'Q3', 'scripts'):
    p = P / d
    touched = [f.relative_to(P).as_posix() for f in p.rglob('*')
               if f.is_file() and f.stat().st_mtime > cutoff]
    print(f'{d:10s} 近 4 小时被改文件数: {len(touched)}', touched[:5])
print('论文/main.tex 引用 drawio 图数:',
      sum(1 for it in m['items']
          if f"{it['name']}.pdf" in (P / '论文' / 'main.tex').read_text(encoding='utf-8')))
