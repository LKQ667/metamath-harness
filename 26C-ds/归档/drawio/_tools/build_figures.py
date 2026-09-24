# -*- coding: utf-8 -*-
"""12 张非数据论文图的 brief / labels 定义。

只做三件事：写 brief.json、写 labels.json、按顺序驱动
drawio_pipeline.py 的 build -> validate -> export。
禁止手写 XML，禁止自造 template_id。
"""
import os
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

SKILL = Path(os.environ.get('MATH_PAPER_HUAWEI_SKILL', 'skills/math-paper-huawei')).resolve()
PIPELINE = SKILL / "scripts" / "drawing" / "drawio_pipeline.py"
PROJECT = Path(__file__).resolve().parents[2]
HAND = PROJECT / "手绘图"

# 字号放大：raw 通道模板自带字号偏小（8–12px），用标签内联 HTML 提升到
# 与六类原创模板（fontSize=14）相当的量级；这是原型模板自身使用的写法。
def big(text: str, px: int = 15) -> str:
    return f'<font style="font-size:{px}px;">{text}</font>'


# ---------------------------------------------------------------------------
# 图定义：(name, kind, brief 结构特征, labels, 章节, 中文用途)
# ---------------------------------------------------------------------------
FIGURES: list[dict] = []


def fig(name, kind, structure, labels, section, title_cn, obj, act, prod, crit,
        nodes, edges, main_path, unverified):
    brief = {
        "name": name,
        "kind": kind,
        "object": obj,
        "action": act,
        "product": prod,
        "criteria": crit,
        "nodes": nodes,
        "edges": edges,
        "main_path": main_path,
        "unverified": unverified,
    }
    brief.update(structure)
    FIGURES.append({
        "name": name, "brief": brief, "labels": labels,
        "section_cn": section, "title_cn": title_cn,
    })


# ===========================================================================
# 总览类
# ===========================================================================

# --- 1. fig_roadmap (kind=roadmap -> panels=2 -> dual-panel-bilevel) --------
fig(
    "fig_roadmap", "roadmap",
    {"panels": 2, "side_head": 0, "output_banner": 0, "focus_stage": 0,
     "feedback": 0, "branches": 0, "actors": 1, "support_blocks": 0,
     "stages": 9, "direction": "horizontal"},
    {
        # 左面板：数据解析、去噪与响应提取
        "left_title": big("第一部分　数据解析、去噪与响应提取", 15),
        "upper_left_iso": big("数据", 12),
        "upper_left_title": big("原始记录与事件解析", 14),
        "upper_left_data_txt": big("数据源", 12),
        "ul_wind": big("四份脑电记录", 12),
        "ul_solar": big("事件解析与分段", 12),
        "ul_gen": big("窄目标化去噪", 12),
        "upper_left_scale_icon": "",
        "upper_left_const_txt": big("准则", 12),
        "ul_const1": big("不做高通与带通", 12),
        "ul_const2": big("心电模板扣除", 12),
        "ul_const3": big("稳健软截断", 12),
        "ul_cost_btn": big("窄目标化去噪流程", 14),
        "ul_formula": big("基线校正 → 心电模板扣除 → 稳健软截断", 13),
        "ul_release_btn": big("输出：干净脑电分段", 14),
        "ul_ll_text1": big("数据交接", 12),
        "ul_ll_text2": big("分段结果", 12),
        "lower_left_las": big("响应", 12),
        "lower_left_title": big("有效视觉响应提取", 14),
        "lower_left_data_txt": big("输入", 12),
        "ll_reg": big("单样本 t 检验", 12),
        "ll_flex": big("BH 错误发现率控制", 11),
        "lower_left_scale_icon": "",
        "lower_left_const_txt": big("输出", 12),
        "ll_const1": big("P300 峰值与潜伏期", 11),
        "ll_const2": big("三高斯分量拟合", 11),
        "ll_const3": big("偏侧指数", 12),
        "ll_rev_btn": big("响应提取与曲线拟合", 14),
        "ll_formula": big("逐点 t 检验 → BH 控制 → 三高斯拟合 → 偏侧指数", 12),
        "ll_dr_btn": big("输出：响应曲线与偏侧指数", 13),
        "da_plan_title": big("问题一产物", 13),
        "da_price_btn": big("干净分段", 12),
        "da_disp_btn": big("响应曲线", 12),
        "da_tl_btn": big("偏侧指数", 12),
        # 右面板：建模、特征判别与认知验证
        "right_title": big("第二部分　多尺度建模与认知验证", 15),
        "ur_iso": big("模型", 12),
        "ur_title": big("多尺度前向计算模型", 14),
        "ur_pred": big("LGN 时空滤波 → 形状选择与除法归一化 → Wilson–Cowan 集群", 13),
        "ur_release": big("Kuramoto 宏观同步与序参数", 14),
        "ur_mr_text": big("尺度递进", 12),
        "mr_las": big("特征", 12),
        "mr_title": big("左右区分特征表示", 14),
        "mr_box1": big("早期窗 Fz 幅值", 12),
        "mr_box2": big("晚期窗 F4−F3 偏侧", 12),
        "mr_box3": big("联合特征向量", 12),
        "mr_dr": big("线性判别分析 → 左右判据", 14),
        "mr_lr_text": big("判别输出", 12),
        "lr_iso": big("认知", 12),
        "lr_title": big("双源认知宏观模型", 14),
        "lr_box1": big("视觉通路 LGN—皮层", 12),
        "lr_box2": big("记忆通路 海马—前额", 12),
        "lr_box3": big("延迟耦合与整合", 12),
        "lr_disp": big("参数辨识与分层验证 → 结论与临床指标", 13),
        "id_plan_title": big("问题二与问题三产物", 13),
        "id_re_btn": big("计算模型", 12),
        "id_disp_btn": big("判别特征", 12),
        "id_ev_btn": big("临床指标", 12),
        "ul_ll_arrow1": "",
        "ul_ll_arrow2": "",
        "ul_ll_arrow3": "",
        "ur_mr_arrow": "",
        "mr_lr_arrow": "",
    },
    "一、问题重述（技术路线总览）",
    "全文技术路线总览：从四份原始脑电记录到结论与临床指标的九级主线，分数据处理与建模验证两个面板",
    "四份原始脑电记录与赛题三问要求",
    "沿数据—响应—模型—特征—认知—验证的主线逐级推进",
    "九级技术路线图，含每级输入输出与三问归属",
    "主线完整、层级清晰、不出现悬空节点",
    ["四份原始脑电记录", "事件解析与分段", "窄目标化去噪", "有效响应提取与曲线拟合",
     "多尺度前向计算模型", "左右区分特征表示", "双源认知宏观模型", "参数辨识与分层验证",
     "结论与临床指标"],
    ["数据→解析", "解析→去噪", "去噪→响应", "响应→模型", "模型→特征", "特征→认知",
     "认知→辨识", "辨识→结论"],
    ["四份原始脑电记录", "事件解析与分段", "窄目标化去噪", "有效响应提取与曲线拟合",
     "多尺度前向计算模型", "左右区分特征表示", "双源认知宏观模型", "参数辨识与分层验证",
     "结论与临床指标"],
    ["模板为结构骨架，节点文字为项目内容；图内不含具体数值结论"],
)

# --- 2. fig_problem_analysis (main-chain-support) --------------------------
fig(
    "fig_problem_analysis", "flowchart",
    {"panels": 1, "side_head": 0, "output_banner": 0, "focus_stage": 0,
     "feedback": 0, "branches": 0, "actors": 1, "support_blocks": 3,
     "stages": 4, "direction": "horizontal"},
    {
        "n1": "视觉刺激",
        "n2": "视网膜与 LGN",
        "n3": "皮层形状区",
        "n4": "头皮三导观测",
        "s1": "问题一：去噪与响应提取",
        "s2": "问题二：机理与特征",
        "s3": "问题三：认知模型与验证",
        "e1": "",
        "e2": "",
        "e3": "",
        "e4": "问题一",
        "e5": "问题二",
        "e6": "问题三",
    },
    "一、问题重述（问题分析）",
    "问题分析流程图：视觉刺激到头皮三导观测的通路，以及三问的任务边界",
    "视觉刺激与三导头皮观测记录",
    "沿视觉通路定位三问各自的作用环节",
    "通路环节与三问任务边界的对应关系图",
    "通路无缺环、三问边界与通路环节对应明确",
    ["视觉刺激", "视网膜与 LGN", "皮层形状区", "头皮三导观测",
     "问题一去噪与响应提取", "问题二机理与特征", "问题三认知模型与验证"],
    ["刺激→视网膜", "视网膜→皮层", "皮层→头皮", "三问支撑通路"],
    ["视觉刺激", "视网膜与 LGN", "皮层形状区", "头皮三导观测"],
    ["三问边界为任务划分，不表示信号的单向流动顺序"],
)

# --- 3. fig_experiment_design (dual-swimlane) ------------------------------
fig(
    "fig_experiment_design", "flowchart",
    {"panels": 1, "side_head": 0, "output_banner": 0, "focus_stage": 0,
     "feedback": 0, "branches": 0, "actors": 2, "support_blocks": 0,
     "stages": 3, "direction": "horizontal"},
    {
        "h1": "采集与通道结构",
        "h2": "项目一与项目二对照",
        "a1": "F3/Fz/F4 三导采集",
        "a2": "10 通道语义分组",
        "a3": "原始信号、设备滤波、心电、事件、时间戳",
        "b1": "项目一：位置已知",
        "b2": "项目二：仅知形状",
        "b3": "一致率约 1.00 与 0.48",
        "e1": "",
        "e2": "",
        "e3": "",
        "e4": "",
        "e5": "同期采集",
        "e6": "条件对照",
    },
    "二、模型假设与符号说明（实验设计）",
    "实验设计与数据结构图：采集通道语义分组，以及项目一与项目二的时序条件对照",
    "项目一与项目二的脑电记录及 10 通道语义分组",
    "对照两个项目的提示条件、时序结构与一致率差异",
    "采集结构说明与两项目对照关系图",
    "通道语义分组完整、两项目条件差异可辨",
    ["F3 / Fz / F4 三导采集", "10 通道语义分组",
     "原始信号、设备滤波、心电、事件、时间戳",
     "项目一提示位置已知", "项目二仅知形状", "一致率约 1.00 与 0.48"],
    ["采集→分组", "分组→通道明细", "项目一→项目二", "两项目条件对照"],
    ["三导采集", "10 通道语义分组", "两项目一致率对照"],
    ["一致率数值取自赛题给定条件，图内只作对照标注"],
)

# ===========================================================================
# 问题一
# ===========================================================================

# --- 4. fig_artifact_sources (main-chain-support) --------------------------
fig(
    "fig_artifact_sources", "flowchart",
    {"panels": 1, "side_head": 0, "output_banner": 0, "focus_stage": 0,
     "feedback": 0, "branches": 0, "actors": 1, "support_blocks": 3,
     "stages": 4, "direction": "horizontal"},
    {
        "n1": "四份脑电记录",
        "n2": "设备量程饱和",
        "n3": "运动与电极瞬变",
        "n4": "心电与慢电位伪迹",
        "s1": "幅值削顶与平台",
        "s2": "尖峰瞬变与漂移",
        "s3": "与心搏同步的波形",
        "e1": "质量诊断",
        "e2": "并列来源",
        "e3": "并列来源",
        "e4": "表现",
        "e5": "表现",
        "e6": "表现",
    },
    "问题一：数据质量与伪迹来源分析",
    "数据质量与伪迹来源分析图：四类伪迹来源及其在记录中的幅值表现",
    "四份原始脑电记录",
    "诊断并归类四类伪迹来源及其幅值表现",
    "伪迹来源与表现形式的对应关系图",
    "四类来源齐全、表现描述与来源一一对应",
    ["四份脑电记录", "设备量程饱和", "运动与电极瞬变", "心电与慢电位伪迹",
     "幅值削顶与平台", "尖峰瞬变与漂移", "与心搏同步的波形"],
    ["诊断→量程饱和", "量程饱和→运动瞬变", "运动瞬变→心电慢电位", "三类表现支撑来源"],
    ["四份脑电记录", "设备量程饱和", "运动与电极瞬变", "心电与慢电位伪迹"],
    ["逐类伪迹的出现比例未在已完成结果中量化，图内只作定性表现描述，不标注比例数值"],
)

# --- 5. fig_q1_denoise_flow (branch-decision) ------------------------------
fig(
    "fig_q1_denoise_flow", "flowchart",
    {"panels": 1, "side_head": 0, "output_banner": 0, "focus_stage": 0,
     "feedback": 0, "branches": 1, "actors": 1, "support_blocks": 0,
     "stages": 4, "direction": "horizontal"},
    {
        "n1": "基线校正与 R 波定位",
        "d1": "心电模板三重判定",
        "n2": "模板扣除",
        "n3": "不做高通与带通",
        "n4": "稳健软截断",
        "e1": "中位模板",
        "e2": "满足：相关度>0.6、幅度>6 倍、增益合理",
        "e3": "不满足",
        "e4": "",
        "e5": "10 倍稳健尺度",
    },
    "问题一：窄目标化去噪流程",
    "窄目标化去噪流程图：基线校正、心电模板三重判定、模板扣除与稳健软截断",
    "去噪后的脑电分段",
    "先校正基线，再按三重条件判定并扣除心电模板，最后做稳健软截断",
    "窄目标化去噪流程与分支判据图",
    "判据阈值完整、分支明确、显式声明不做高通与带通",
    ["基线校正与 R 波定位", "心电模板三重判定", "模板扣除", "不做高通与带通", "稳健软截断"],
    ["校正→判定", "判定满足→模板扣除", "判定不满足→不做高通带通", "两分支→稳健软截断"],
    ["基线校正与 R 波定位", "心电模板三重判定", "模板扣除", "稳健软截断"],
    ["阈值与 10 倍稳健尺度取自已完成的去噪强度扫描记录"],
)

# --- 6. fig_q1_response_flow (horizontal-stage-chain) ----------------------
fig(
    "fig_q1_response_flow", "flowchart",
    {"panels": 1, "side_head": 0, "output_banner": 0, "focus_stage": 0,
     "feedback": 0, "branches": 0, "actors": 1, "support_blocks": 0,
     "stages": 5, "direction": "horizontal"},
    {
        "n1": "逐点单样本 t 检验",
        "n2": "BH 错误发现率控制",
        "n3": "P300 与早期窗峰潜伏期",
        "n4": "三高斯分量最小二乘拟合",
        "n5": "偏侧指数",
        "e1": "",
        "e2": "",
        "e3": "",
        "e4": "",
    },
    "问题一：有效视觉响应提取与曲线拟合",
    "有效视觉响应提取与曲线拟合流程图：显著性检验、错误发现率控制、峰值潜伏期与三高斯拟合",
    "去噪后的分段脑电",
    "先做逐点显著性检验与错误发现率控制，再提取峰值潜伏期并拟合三高斯分量",
    "响应提取与曲线拟合流程及偏侧指数导出图",
    "检验、控制、提取、拟合、导出五步齐全且顺序正确",
    ["逐点单样本 t 检验", "BH 错误发现率控制", "P300 与早期窗峰潜伏期",
     "三高斯分量最小二乘拟合", "偏侧指数"],
    ["检验→控制", "控制→峰值潜伏期", "潜伏期→三高斯拟合", "拟合→偏侧指数"],
    ["逐点单样本 t 检验", "BH 错误发现率控制", "三高斯分量最小二乘拟合", "偏侧指数"],
    ["各窗峰值与潜伏期的具体数值由问题一结果文件给出，图内不重复"],
)

# ===========================================================================
# 问题二
# ===========================================================================

# --- 7. fig_q2_multiscale_model (dual-swimlane, 横向 2.72:1) ---------------
# 原用纵向分层链导出为 526×1346（宽高比 0.39），插入论文后近半页高；改用横向
# 双泳道模板（内容框 940×345，宽高比 2.72），仍用 build --brief 原子生成。
fig(
    "fig_q2_multiscale_model", "flowchart",
    {"panels": 1, "side_head": 0, "output_banner": 0, "focus_stage": 0,
     "feedback": 0, "branches": 0, "actors": 2, "support_blocks": 0,
     "stages": 5, "direction": "horizontal"},
    {
        "h1": "五级串联 · 前三级：微观与介观",
        "h2": "五级串联 · 后两级：宏观与观测",
        "a1": "LGN 时空滤波（毫秒级）",
        "a2": "形状选择与除法归一化（十毫秒级）",
        "a3": "Wilson–Cowan 介观集群（百毫秒级）",
        "b1": "Kuramoto 同步与序参数（秒级）",
        "b2": "头皮导联场观测",
        "b3": "尺度跨度：毫秒 → 秒",
        "e1": "",
        "e2": "",
        "e3": "",
        "e4": "",
        "e5": "层间衔接",
        "e6": "层间衔接",
    },
    "问题二：多尺度脑电计算模型机理",
    "多尺度脑电计算模型机理框图：五级串联结构及各级时间尺度与数学对象",
    "头皮三导观测信号",
    "由介观集群与宏观同步逐级前向计算得到头皮观测",
    "横向五级串联机理框图，各级标注时间尺度与数学对象",
    "五级齐全、时间尺度单调递进、层级对象明确",
    ["LGN 时空滤波", "形状选择与除法归一化", "Wilson–Cowan 介观集群",
     "Kuramoto 同步与序参数", "头皮导联场观测"],
    ["滤波→形状选择", "形状选择→介观集群", "介观集群→宏观同步", "宏观同步→头皮观测"],
    ["LGN 时空滤波", "形状选择与除法归一化", "Wilson–Cowan 介观集群",
     "Kuramoto 同步与序参数", "头皮导联场观测"],
    ["时间尺度为各级的定性量级标注，非拟合得到的数值",
     "第 6 个内容框为尺度跨度汇总标注，不引入新的计算层级"],
)

# --- 8. fig_q2_laterality_mechanism (main-chain-support) -------------------
fig(
    "fig_q2_laterality_mechanism", "flowchart",
    {"panels": 1, "side_head": 0, "output_banner": 0, "focus_stage": 0,
     "feedback": 0, "branches": 0, "actors": 1, "support_blocks": 3,
     "stages": 4, "direction": "horizontal"},
    {
        "n1": "右指三角源分布",
        "n2": "水平镜像映射",
        "n3": "左指三角源分布",
        "n4": "差分 F4−F3 判据",
        "s1": "Fz 位于中线相消",
        "s2": "F3/F4 权重互换",
        "s3": "镜像差异最敏感",
        "e1": "",
        "e2": "",
        "e3": "",
        "e4": "支撑",
        "e5": "校验",
        "e6": "约束",
    },
    "问题二：左右三角刺激皮层响应镜像分布形成机制",
    "左右三角刺激皮层响应镜像分布形成机制图：镜像映射与三导联权重关系",
    "右指与左指三角刺激的皮层响应",
    "以水平镜像解释左右源分布差异，并说明三导联对镜像差异的敏感度",
    "镜像分布机制与导联权重关系图",
    "镜像关系正确、Fz 相消与 F3/F4 权重互换表述准确",
    ["右指三角源分布", "水平镜像映射", "左指三角源分布", "差分 F4−F3 判据",
     "Fz 位于中线相消", "F3/F4 权重互换", "镜像差异最敏感"],
    ["右指源→镜像映射", "镜像映射→左指源", "左指源→差分判据", "三条机制支撑"],
    ["右指三角源分布", "水平镜像映射", "左指三角源分布", "差分 F4−F3 判据"],
    ["机制为模型解释，未在数据上做因果实验验证"],
)

# --- 9. fig_q2_feature_flow (horizontal-stage-chain) -----------------------
fig(
    "fig_q2_feature_flow", "flowchart",
    {"panels": 1, "side_head": 0, "output_banner": 0, "focus_stage": 0,
     "feedback": 0, "branches": 0, "actors": 1, "support_blocks": 0,
     "stages": 5, "direction": "horizontal"},
    {
        "n1": "早期窗 Fz 幅值（80–250 ms）",
        "n2": "晚期窗 F4−F3 偏侧（250–800 ms）",
        "n3": "联合特征向量",
        "n4": "线性判别分析",
        "n5": "左右判据",
        "e1": "",
        "e2": "",
        "e3": "",
        "e4": "",
    },
    "问题二：形状—空间联合特征表示与判别",
    "形状—空间联合特征表示与判别流程图：早期形状编码与晚期空间编码的联合判别",
    "早期窗与晚期窗的导联特征",
    "先分别构造形状编码与空间编码，再拼接为联合特征向量并做线性判别",
    "联合特征表示与判别流程图",
    "两个编码窗口正确、联合与判别顺序正确",
    ["早期窗 Fz 幅值", "晚期窗 F4−F3 偏侧", "联合特征向量", "线性判别分析", "左右判据"],
    ["早期窗→晚期窗", "晚期窗→联合向量", "联合向量→判别分析", "判别分析→左右判据"],
    ["早期窗 Fz 幅值", "晚期窗 F4−F3 偏侧", "联合特征向量", "线性判别分析", "左右判据"],
    ["窗内取值与判别准确率由问题二结果文件给出，图内不重复"],
)

# ===========================================================================
# 问题三
# ===========================================================================

# --- 10. fig_q3_model_framework (main-chain-support) ----------------------
fig(
    "fig_q3_model_framework", "flowchart",
    {"panels": 1, "side_head": 0, "output_banner": 0, "focus_stage": 0,
     "feedback": 0, "branches": 0, "actors": 1, "support_blocks": 3,
     "stages": 4, "direction": "horizontal"},
    {
        "n1": "LGN—皮层视觉通路",
        "n2": "海马—前额记忆通路",
        "n3": "延迟耦合与前额整合",
        "n4": "头皮导联观测",
        "s1": "延迟 τ_H",
        "s2": "增益 g_H",
        "s3": "窗口终点：应答前 100 ms",
        "e1": "双源并列",
        "e2": "延迟耦合",
        "e3": "前向观测",
        "e4": "延迟",
        "e5": "增益",
        "e6": "窗口",
    },
    "问题三：双源认知宏观模型框架",
    "双源认知宏观模型框架图：视觉通路与记忆通路的延迟耦合、前额整合与头皮观测",
    "视觉通路与记忆通路两路输入",
    "以延迟耦合与前额整合连接双源，并输出头皮观测",
    "双源认知宏观模型框架图",
    "双源、延迟、增益、整合与观测五要素齐全",
    ["LGN—皮层视觉通路", "海马—前额记忆通路", "延迟耦合与前额整合", "头皮导联观测",
     "延迟 τ_H", "增益 g_H", "窗口终点：应答前 100 ms"],
    ["视觉通路→记忆通路", "记忆通路→整合", "整合→头皮观测", "参数支撑整合与观测"],
    ["LGN—皮层视觉通路", "海马—前额记忆通路", "延迟耦合与前额整合", "头皮导联观测"],
    ["符合项的具体形式与参数取值由问题三结果文件给出，图内只标物理含义"],
)

# --- 11. fig_q3_estimation_flow (horizontal-stage-chain) ------------------
fig(
    "fig_q3_estimation_flow", "flowchart",
    {"panels": 1, "side_head": 0, "output_banner": 0, "focus_stage": 0,
     "feedback": 0, "branches": 0, "actors": 1, "support_blocks": 0,
     "stages": 5, "direction": "horizontal"},
    {
        "n1": "认知窗口截取",
        "n2": "参数初始化与区间约束",
        "n3": "加权残差与正则化",
        "n4": "扰动扫描与可辨识性",
        "n5": "分层验证与设备对照",
        "e1": "",
        "e2": "",
        "e3": "",
        "e4": "",
    },
    "问题三：认知模型参数估计与验证",
    "认知模型参数估计与验证流程图：窗口截取、约束优化、可辨识性评估与分层验证",
    "认知窗口内的头皮观测",
    "在物理区间约束下最小化加权残差，再做可辨识性与分层验证",
    "参数估计与验证流程图",
    "估计与验证环节齐全、约束与分层口径明确",
    ["认知窗口截取", "参数初始化与区间约束", "加权残差与正则化",
     "扰动扫描与可辨识性", "分层验证与设备对照"],
    ["截取→初始化", "初始化→残差最小化", "最小化→可辨识性", "可辨识性→分层验证"],
    ["认知窗口截取", "参数初始化与区间约束", "加权残差与正则化",
     "扰动扫描与可辨识性", "分层验证与设备对照"],
    ["参数估计值与可辨识性指标由问题三结果文件给出，图内不重复"],
)

# --- 12. fig_q3_application (main-chain-support) --------------------------
fig(
    "fig_q3_application", "flowchart",
    {"panels": 1, "side_head": 0, "output_banner": 0, "focus_stage": 0,
     "feedback": 0, "branches": 0, "actors": 1, "support_blocks": 3,
     "stages": 4, "direction": "horizontal"},
    {
        "n1": "双源认知宏观模型",
        "n2": "记忆回路维持强度 Φ",
        "n3": "τ_H 与 g_H 病程趋势",
        "n4": "临床指标与评价",
        "s1": "模型局限",
        "s2": "改进方向",
        "s3": "后续验证",
        "e1": "导出",
        "e2": "病程演变",
        "e3": "评价",
        "e4": "局限",
        "e5": "改进",
        "e6": "验证",
    },
    "模型总结与评价（应用与临床指标）",
    "模型体系结构、评价与临床指标图：导出指标随病程的定性趋势及模型局限与改进",
    "双源认知宏观模型与其导出指标",
    "由模型导出记忆回路维持强度指标并给出病程定性趋势与局限改进",
    "模型评价与临床指标导出图",
    "导出链路完整、趋势标注为定性、局限与改进并列",
    ["双源认知宏观模型", "记忆回路维持强度 Φ", "τ_H 与 g_H 病程趋势", "临床指标与评价",
     "模型局限", "改进方向", "后续验证"],
    ["模型→维持强度指标", "指标→病程趋势", "趋势→临床评价", "局限改进支撑评价"],
    ["双源认知宏观模型", "记忆回路维持强度 Φ", "τ_H 与 g_H 病程趋势", "临床指标与评价"],
    ["病程趋势为模型导出的定性关系，未在患者队列数据上验证，图内不做定量外推"],
)


# ---------------------------------------------------------------------------
def run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(PIPELINE), *args],
                          text=True, encoding="utf-8", errors="replace",
                          capture_output=True)


def main() -> int:
    HAND.mkdir(parents=True, exist_ok=True)
    results = []
    for entry in FIGURES:
        name = entry["name"]
        brief_path = HAND / f"{name}_brief.json"
        labels_path = HAND / f"{name}_labels.json"
        source = HAND / f"{name}.drawio"
        labels = dict(entry["labels"])
        # 六类原创模板的 vertex_style 固定 fontSize=14，在约 1000pt 宽的图上按
        # 正文宽度插入后仅约 6pt。用标签内联 HTML 提升字号（raw 模板同款机制），
        # 使正文宽度插入后约 8–9pt、双栏缩印仍可读。
        if entry["brief"]["kind"] != "roadmap":
            labels = {
                k: (big(v, 12) if re.match(r"^e\d+$", k) else big(v, 17))
                for k, v in labels.items() if v
            }
        brief_path.write_text(json.dumps(entry["brief"], ensure_ascii=False, indent=2), encoding="utf-8")
        labels_path.write_text(json.dumps(labels, ensure_ascii=False, indent=2), encoding="utf-8")

        built = run(["build", "--brief", str(brief_path), "--labels-json", str(labels_path),
                     "--output", str(source)])
        record = {"name": name, "build_exit": built.returncode}
        try:
            payload = json.loads(built.stdout.strip().splitlines()[-1])
        except Exception:
            record["build_stdout"] = built.stdout[-2000:]
            record["build_stderr"] = built.stderr[-2000:]
            results.append(record)
            print(json.dumps(record, ensure_ascii=False))
            continue
        template_id = payload["template_id"]
        record["template_id"] = template_id
        record["build_ok"] = payload["ok"]
        record["build_errors"] = payload["errors"]

        val = run(["validate", str(source), "--template", template_id])
        record["validate_exit"] = val.returncode
        try:
            record["validate"] = json.loads(val.stdout.strip())
        except Exception:
            record["validate_raw"] = val.stdout[-2000:]
        results.append(record)
        print(json.dumps(record, ensure_ascii=False))

    (HAND / "_tools" / "build_summary.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    bad = [r for r in results if r.get("build_exit") != 0 or r.get("validate_exit") != 0]
    print(f"\nBUILD/VALIDATE FAILURES: {len(bad)} / {len(results)}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
