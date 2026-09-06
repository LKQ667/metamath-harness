#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_abstract.py 自动化单元测试套件
测试包含：合规国一范例测试、LaTeX模板片段测试、独立公式拦截测试、字数过少拦截测试、未规范加粗拦截测试、AI腔调预警测试。
"""

import sys
from pathlib import Path

# 引入被测模块
sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_abstract import run_all_checks


# 1. 黄金标准国奖范例 (Markdown 格式，约 920 汉字)
GOLDEN_ABSTRACT_MD = """
塔式太阳能光热发电是一种具有广阔应用前景的大规模利用太阳能发电的成熟技术。定日镜是其收集太阳能的核心基本组件，通过数学建模优化定日镜场排布参数，使单位镜面面积年平均输出热功率最大化，对提升光热电站整体综合效益具有关键现实意义。本文从光学反射机理与空间坐标转换方程出发，综合建立定日镜场几何光学仿真模型与非线性单目标参数优化模型，并结合启发式全局搜索算法展开求解。

**针对问题一：** 建立定日镜场年平均输出热功率精确计算模型。首先依据太阳天顶角与方位角变化规律建立太阳入射光线矢量方程，通过镜面法向量空间变换计算镜面俯仰角与方位角；其次推导镜场几何坐标变换矩阵 $T$，将阴影遮挡划分为塔遮挡、相邻镜遮挡与受光面遮挡三类几何损失，结合锥形光线离散采样与蒙特卡洛投点法，计算集热器对反射光斑的截断效率，进而推导定日镜场的光学效率随季节和日照时刻的演化关系。最终求得该基准镜场的年平均光学效率为 **0.6275**，年平均输出热功率为 **38.295 MW**，单位镜面面积年平均输出热功率为 **0.6096 kW/m²**，完整月度数据详见正文表 1 与表 2。

**针对问题二：** 建立定日镜场统一尺寸排布的单目标非线性规划模型。以单位镜面面积年平均输出热功率最大化为目标函数，将吸收塔坐标 $(X, Y)$、定日镜统一定制长宽尺寸、安装高度以及相邻镜面安全间距设为决策变量。针对高维非凸解空间特征，设计自适应变步长动态搜索算法配合局部精细遍历进行求解，通过动态调整网格步长避免算法陷入局部极值陷阱。计算结果表明：吸收塔最优安装坐标定位于 **(0, -79)**，镜面统一规格为 **5.5 m × 5.5 m**，最佳安装高度为 **2.75 m**，镜面总面数为 **3385** 面，年平均输出热功率显著提高至 **60.1189 MW**，单位面积年均热功率达到 **0.5871 kW/m²**，优化参数汇总于 `result2.xlsx`。

**针对问题三：** 打破统一尺寸约束，构建定日镜场非统一规格分区域规划的单目标优化模型。根据镜场径向距离与光学衰减梯度，将环形镜场划分为多层同心圆环区域，各区域分别配置独立的镜面尺寸与安装高度。在同心圆排布拓扑基础上，采用二次规划结合自适应遗传算法联合优化各圈层参数，通过染色体分段编码加快搜索收敛进程。最终求解得到最优定日镜总面数为 **2846** 面，共包含 7 种不同安装高度组合，此时单位镜面面积年均输出热功率最高达 **0.7551 kW/m²**，年平均输出热功率达到 **60.359 MW**，整体镜场形成渐进阶梯状抛物面分布，详细设计方案列于 `result3.xlsx`。

**关键词：** 定日镜场；光学效率；蒙特卡洛投点；单目标优化；变步长搜索
"""

# 2. 缺陷样本 A：包含独立公式环境
SAMPLE_BAD_EQUATION = """
**针对问题一：** 建立运动学方程如下：
\\begin{equation}
s(t) = \\int_0^t v(\\tau) d\\tau
\\end{equation}
求解得到最终速度。
"""

# 3. 缺陷样本 B：字数严重偏少 (< 750 字)
SAMPLE_BAD_TOO_SHORT = """
**针对问题一：** 建立了模型一，求解了速度，结果为 1.2 m/s。
**针对问题二：** 建立了模型二，求解了位置，结果为 3.4 m。
**针对问题三：** 进行了优化，获得了最优方案。
**关键词：** 模型；优化；速度
"""

# 4. 缺陷样本 C：未规范加粗（冒号在外面，或使用了逗号）
SAMPLE_BAD_BOLDING = """
这是一篇数学建模摘要引言内容，字数比较充实，用于测试标签格式检测。
**针对问题一**：建立了第一问模型，计算得到结果为 12.5 m。
针对问题二，建立了第二问模型，计算得到结果为 34.8 m。
针对问题三：建立了第三问模型，计算得到结果为 56.1 m。
**关键词：** 符号；测试；指标
"""

# 5. 缺陷样本 D：高频 AI 腔调与机械顺承词
SAMPLE_BAD_AI_STYLE = """
针对问题一：首先进行了数据清洗，其次建立了神经网络模型，然后设计了革命性算法，接着进行了颠覆性优化，最后取得了十分显著且令人瞩目的优异成果，显著提升了鲁棒性。众所周知，由此可知该模型具有极具推广价值。
"""


def test_golden_sample():
    print("[测试 1] 验证黄金标准国奖范例...")
    res = run_all_checks(GOLDEN_ABSTRACT_MD)
    assert res["passed"], f"黄金样本质检未通过: {res['errors']}"
    assert 850 <= res["char_count"] <= 1050, f"字数不在黄金区间: {res['char_count']}"
    assert res["bolding_status"]["compliant"], "未检测到合规的问题加粗标签"
    assert len(res["equation_violations"]) == 0, "误报独立公式"
    print(f"  -> 通过！字数: {res['char_count']}, 定量指标: {res['numerical_density']['count']} 处")


def test_latex_snippet():
    print("[测试 2] 验证 LaTeX 模板片段...")
    snippet_path = Path(__file__).resolve().parents[1] / "references" / "latex-abstract-snippet.tex"
    snippet_text = snippet_path.read_text(encoding="utf-8")
    res = run_all_checks(snippet_text)
    assert res["passed"], f"LaTeX 模板质检未通过: {res['errors']}"
    assert len(res["equation_violations"]) == 0, "LaTeX 模板误报独立公式"
    assert res["bolding_status"]["compliant"], "LaTeX 模板未检测到 \\paperstrong{针对问题X：}"
    print(f"  -> 通过！提取字数: {res['char_count']}")


def test_equation_interception():
    print("[测试 3] 验证独立公式拦截能力...")
    res = run_all_checks(SAMPLE_BAD_EQUATION)
    assert not res["passed"], "应当拦截包含独立公式的样本"
    assert any("独立公式" in err for err in res["errors"]), f"未给出独立公式错误提示: {res['errors']}"
    print("  -> 通过！精准拦截独立公式环境。")


def test_short_length_interception():
    print("[测试 4] 验证字数过少拦截能力...")
    res = run_all_checks(SAMPLE_BAD_TOO_SHORT)
    assert not res["passed"], "应当拦截字数过少的样本"
    assert any("字数严重偏少" in err for err in res["errors"]), f"未给出字数过少错误提示: {res['errors']}"
    print("  -> 通过！精准拦截字数过少缺陷。")


def test_bolding_interception():
    print("[测试 5] 验证未规范加粗拦截能力...")
    res = run_all_checks(SAMPLE_BAD_BOLDING)
    assert not res["passed"], "应当拦截冒号未加粗或未加粗的问题标签"
    assert any("问题标签格式未规范加粗" in err for err in res["errors"]), f"未给出加粗错误提示: {res['errors']}"
    print("  -> 通过！精准拦截标签格式错误。")


def test_ai_style_warning():
    print("[测试 6] 验证 AI 腔调与死板顺承词警告能力...")
    res = run_all_checks(SAMPLE_BAD_AI_STYLE)
    assert len(res["warnings"]) >= 2, f"应当对 AI 词和顺承词发出警告: {res['warnings']}"
    warn_text = " ".join(res["warnings"])
    assert "AI 腔调" in warn_text, "未检测出 AI 虚假吹嘘词"
    assert "顺承词" in warn_text, "未检测出死板顺承词链"
    print("  -> 通过！精准报警 AI 模式化腔调。")


def main():
    print("================ 开始执行 check_abstract 自动化全量测试 ================")
    try:
        test_golden_sample()
        test_latex_snippet()
        test_equation_interception()
        test_short_length_interception()
        test_bolding_interception()
        test_ai_style_warning()
        print("================ 所有测试用例 100% 执行通过 (PASS) ================")
        return 0
    except AssertionError as e:
        print(f"\n[测试失败] {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
