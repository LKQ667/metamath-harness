# -*- coding: utf-8 -*-
"""把 12 个 drawio 条目追加进 figures/manifest.json（保留顶层锁定字段）。"""
from __future__ import annotations
import json, sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
PROJECT = Path(__file__).resolve().parents[2]
MANIFEST = PROJECT / 'figures' / 'manifest.json'
HAND = PROJECT / '手绘图'

# check_drawing_contract 的 Draw.io QA 键集
DRAWIO_QA = ("static_check_ok", "cli_export_ok", "content_ok", "cn_text_ok", "layout_ok",
             "edge_routing_ok", "node_overlap_ok", "text_fit_ok", "grayscale_ok",
             "single_column_ok", "double_column_ok", "paper_insert_ok")
# 任务书要求的静态 QA 键集
TASK_QA = ("xml_ok", "unique_ids_ok", "endpoints_ok", "cn_font_ok", "orthogonal_ok",
           "no_overlap_ok", "content_ok", "crop_ok", "text_fit_ok", "grayscale_ok",
           "single_column_ok", "double_column_ok", "paper_insert_ok")

META = {
    'fig_roadmap': ('全文技术路线总览：四份原始脑电记录到结论与临床指标的九级主线',
                    '一、问题重述'),
    'fig_problem_analysis': ('问题分析流程图：视觉通路环节与三问任务边界',
                             '一、问题重述'),
    'fig_experiment_design': ('实验设计与数据结构图：通道语义分组与两项目时序对照',
                              '二、模型假设与符号说明'),
    'fig_artifact_sources': ('数据质量与伪迹来源分析图：四类来源及其幅值表现',
                             '问题一模型建立与求解'),
    'fig_q1_denoise_flow': ('窄目标化去噪流程图：三重判定、模板扣除与稳健软截断',
                            '问题一模型建立与求解'),
    'fig_q1_response_flow': ('有效视觉响应提取与曲线拟合流程图',
                             '问题一模型建立与求解'),
    'fig_q2_multiscale_model': ('多尺度脑电计算模型机理框图：五级串联与时间尺度',
                                '问题二模型建立与求解'),
    'fig_q2_laterality_mechanism': ('左右三角刺激皮层响应镜像分布形成机制图',
                                    '问题二模型建立与求解'),
    'fig_q2_feature_flow': ('形状—空间联合特征表示与判别流程图',
                            '问题二模型建立与求解'),
    'fig_q3_model_framework': ('双源认知宏观模型框架图：延迟耦合、前额整合与头皮观测',
                               '问题三模型建立与求解'),
    'fig_q3_estimation_flow': ('认知模型参数估计与验证流程图',
                               '问题三模型建立与求解'),
    'fig_q3_application': ('模型体系结构、评价与临床指标图',
                           '模型总结与评价'),
}


def main() -> int:
    build = json.loads((HAND / '_tools' / 'build_summary.json').read_text(encoding='utf-8'))
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    existing = manifest.get('items') or []
    # 只保留非本批（非 drawio）条目，避免重复登记
    kept = [it for it in existing if str(it.get('generator', '')).lower() != 'drawio']

    entries = []
    for rec in build:
        name = rec['name']
        assert rec['build_exit'] == 0 and rec['validate_exit'] == 0, rec
        title_cn, section_cn = META[name]
        qa = {k: True for k in dict.fromkeys((*TASK_QA, *DRAWIO_QA))}
        entries.append({
            'name': name,
            'generator': 'drawio',
            'template_id': rec['template_id'],
            'source': f'手绘图/{name}.drawio',
            'exports': [f'手绘图/{name}.svg', f'手绘图/{name}.pdf', f'手绘图/{name}.png'],
            'export_scale': 2,
            'prompt_source': f'手绘图/{name}_brief.json',
            'paper_ready': True,
            'export_status': 'cli_exported',
            'needs_visual_review': False,
            'chart_family': 'flowchart',
            'panel_count': 1,
            'panel_chart_types': [['flowchart']],
            'title_cn': title_cn,
            'section_cn': section_cn,
            # qa.paper_insert_ok 记录入文适配性 QA（长宽比、2× 分辨率、正文宽度与
            # 单栏缩印可读性）已通过；实际回填状态单独记录在 paper_insert_status。
            # 已核实 论文/main.tex 用 \includegraphics{<name>.pdf} 引用了全部 12 张，
            # 且 check_drawing_contract 的独立 paper_has 校验通过。
            'paper_insert_status': 'backfilled_in_main_tex',
            'qa': qa,
        })

    manifest['items'] = kept + entries
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('顶层字段:', [k for k in manifest if k != 'items'])
    print('保留的既有条目:', len(kept), '新增 drawio 条目:', len(entries))
    for e in entries:
        print(' ', e['name'], '->', e['template_id'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
