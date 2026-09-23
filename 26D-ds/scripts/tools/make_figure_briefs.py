# -*- coding: utf-8 -*-
"""生成手绘图图稿摘要（设计简报），供 manifest 的 prompt_source 字段追溯。

图稿摘要放在 手绘图/图稿摘要/ 子目录，避免被门禁计入手绘图根目录的概念类提示词数量。

运行：python scripts/tools/make_figure_briefs.py
"""
from __future__ import annotations

import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "手绘图", "图稿摘要")

BRIEFS = {
    "技术路线图": {
        "kind": "roadmap",
        "对象": "四问协同的整体技术路线",
        "动作": "数据底座 → 问题一能力与组批 → 问题二三调度与通信 → 问题四分区与资源配置",
        "产物": "各阶段方法要点与结论回流关系",
        "判据": "结构指纹与骨架池一致；中文无乱码；节点不重叠；单栏缩印可读",
        "节点": "4 行阶段带 × 4 列方法卡，左侧竖向阶段标签，行间向下箭头",
        "边": "行间主路径箭头；底部虚线结论回流带",
        "主路径": "数据底座 → 问题一 → 问题二三 → 问题四 → 结论回流",
        "未证实内容": "无（全部取自本项目已完成的模型与结果）",
        "结构特征": {"kind": "roadmap", "stages": 4, "direction": "vertical",
                     "feedback": 1, "branches": 0, "actors": 3, "panels": 0,
                     "side_head": 1, "output_banner": 1, "focus_stage": 0,
                     "support_blocks": 1},
        "骨架": "skeleton_spine",
    },
    "问题分析流程图": {
        "kind": "flowchart",
        "对象": "四问的问题分解、约束识别与耦合关系",
        "动作": "总问题拆解 → 各问核心决策与约束 → 耦合与数据继承 → 公共物理口径",
        "产物": "四问的决策变量、约束清单、求解方法与继承关系",
        "判据": "四列卡片等宽对齐；中文无乱码；无溢出越界",
        "节点": "顶部总问题横幅 + 4 列问题卡 + 4 格耦合条 + 3 格公共口径条",
        "边": "横幅到卡片组、卡片组到耦合条、耦合条到口径条的向下箭头",
        "主路径": "总问题 → 四问分解 → 耦合继承 → 公共口径",
        "未证实内容": "无",
        "结构特征": {"kind": "flowchart", "stages": 4, "direction": "vertical",
                     "feedback": 0, "branches": 4, "actors": 4, "panels": 4,
                     "side_head": 0, "output_banner": 1, "focus_stage": 0,
                     "support_blocks": 2},
        "骨架": "skeleton_layered",
    },
    "运输中继协同调度框架图": {
        "kind": "framework",
        "对象": "运输层、通信层、资源层的三层协同与信息流",
        "动作": "架次构造与排程 → 轨迹采样与链路判定 → 机队与能源周转",
        "产物": "层间耦合关系、直连可用性判据、中继布点与机队规模结论",
        "判据": "三层纵向对齐；耦合箭头方向明确；中文无乱码",
        "节点": "3 行层带 × 4 列方法卡 + 3 格层间耦合条 + 3 格结论条",
        "边": "层间双向箭头（缺口下传、窗口上传；能耗回写、就绪上传）",
        "主路径": "运输层 → 通信层 → 资源层 → 结论",
        "未证实内容": "无",
        "结构特征": {"kind": "flowchart", "stages": 3, "direction": "vertical",
                     "feedback": 2, "branches": 0, "actors": 3, "panels": 0,
                     "side_head": 0, "output_banner": 1, "focus_stage": 0,
                     "support_blocks": 2},
        "骨架": "skeleton_layered",
    },
    "组批求解流程图": {
        "kind": "flowchart",
        "对象": "问题一的求解链路",
        "动作": "输入汇总 → 四阶段求解 → 四类输出",
        "产物": "最大安全载荷、组批方案、权衡前沿、临界返航余量",
        "判据": "阶段卡等宽；回环虚线框表示迭代；中文无乱码",
        "节点": "顶部输入条 + 4 张阶段卡（含 2 个回环框）+ 4 格输出条",
        "边": "输入到阶段的箭头、阶段间右向箭头、阶段到输出的向下箭头",
        "主路径": "输入 → 二分求载荷 → 组批动态规划 → 前沿与灵敏度 → 输出",
        "未证实内容": "无",
        "结构特征": {"kind": "flowchart", "stages": 4, "direction": "horizontal",
                     "feedback": 2, "branches": 0, "actors": 1, "panels": 4,
                     "side_head": 0, "output_banner": 1, "focus_stage": 0,
                     "support_blocks": 2},
        "骨架": "skeleton_twocolumn",
    },
    "任务分区评估流程图": {
        "kind": "flowchart",
        "对象": "问题四的分区与资源评估链路",
        "动作": "基准冻结 → 两种分区生成 → 逐组独立核算 → 冗余与缺口判定 → 四维比较",
        "产物": "2 组与 3 组方案、资源需求、冗余量、缺口与成因",
        "判据": "分支判定框清晰；两条分支对称；中文无乱码",
        "节点": "顶部基准条 + 4 张阶段卡 + 判定框 + 2 条分支 + 4 格比较条",
        "边": "纵向主链箭头与判定后的左右分支箭头",
        "主路径": "基准 → 分区 → 独立核算 → 判定 → 缺口或冗余 → 四维比较",
        "未证实内容": "无",
        "结构特征": {"kind": "flowchart", "stages": 4, "direction": "vertical",
                     "feedback": 0, "branches": 2, "actors": 4, "panels": 4,
                     "side_head": 0, "output_banner": 1, "focus_stage": 0,
                     "support_blocks": 2},
        "骨架": "skeleton_swimlane",
    },
}


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    for name, b in BRIEFS.items():
        lines = [f"# 图稿摘要：{name}", ""]
        for key in ("kind", "对象", "动作", "产物", "判据", "节点", "边",
                    "主路径", "未证实内容"):
            lines.append(f"- {key}：{b[key]}")
        lines.append("")
        lines.append("## 结构特征（供骨架选择器读取）")
        for k, v in b["结构特征"].items():
            lines.append(f"- {k}：{v}")
        lines.append("")
        lines.append(f"- 选用骨架：{b['骨架']}")
        path = os.path.join(OUT, f"{name}.md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        print("写出", os.path.relpath(path, ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())