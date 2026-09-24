# -*- coding: utf-8 -*-
"""残留非中文/模板遗留文字检查 + 节点文字长度检查。"""
from __future__ import annotations
import json, re, sys, xml.etree.ElementTree as ET
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
HAND = Path(__file__).resolve().parents[2] / '手绘图'

# 允许出现的拉丁/符号记号：赛题与模型的标准写法
ALLOWED = {
    'LGN', 'Fz', 'F3', 'F4', 'BH', 'P300', 'Wilson', 'Cowan', 'Kuramoto',
    't', 'ms', 'font', 'style', 'px', 'br',
}
CJK = re.compile(r'[\u4e00-\u9fff]')
LATIN_RUN = re.compile(r'[A-Za-z]{2,}')

def strip_html(v: str) -> str:
    return re.sub(r'<[^>]+>', '', v)

rows = []
problems = []
for path in sorted(HAND.glob('*.drawio')):
    root = ET.parse(path).getroot()
    for cell in root.findall('.//mxCell'):
        value = cell.get('value') or ''
        if not value.strip():
            continue
        plain = strip_html(value)
        cid = cell.get('id')
        # 1) 残留模板英文
        runs = [m.group(0) for m in LATIN_RUN.finditer(plain) if m.group(0) not in ALLOWED]
        if runs:
            problems.append({'file': path.name, 'id': cid, 'kind': 'residual_latin',
                             'runs': runs, 'value': plain})
        # 2) 非中文且无 CJK（纯符号/数字节点，可能是遗留装饰）
        if not CJK.search(plain):
            problems.append({'file': path.name, 'id': cid, 'kind': 'no_cjk',
                             'value': plain})
        # 3) 节点汉字数 > 16
        if cell.get('vertex') == '1':
            n = len(CJK.findall(plain))
            if n > 16:
                problems.append({'file': path.name, 'id': cid, 'kind': 'too_long',
                                 'cjk': n, 'value': plain})
        rows.append((path.name, cid, plain))

print('总文本单元:', len(rows))
print('问题数:', len(problems))
for p in problems:
    print(' ', json.dumps(p, ensure_ascii=False))
(HAND / '_tools' / 'text_audit.json').write_text(
    json.dumps({'cells': len(rows), 'problems': problems}, ensure_ascii=False, indent=2),
    encoding='utf-8')
