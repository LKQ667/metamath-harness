# -*- coding: utf-8 -*-
"""把正文中体量最大的纯数据表移入附录，并在附录补入组批方案明细。

改动范围（其余内容不变）：
1. 正文“三种机型在各服务区的最大安全载荷”表移入附录 A，正文改为引用并保留关键数值；
2. 正文“中继机队规模对联合调度可行性的影响”表移入附录 C，正文改为引用；
3. 附录 A 新增“各服务区组批方案明细”表，数据取自 results/q1_results.json；
4. 附录小节顺次为 A 问题一、B 问题二、C 问题三、D 问题四。
"""
import io
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MAIN = os.path.join(ROOT, "论文", "main.tex")
RESULTS = os.path.join(ROOT, "results")

APPENDIX_A_HEAD = """\\section{问题一附录}

限于篇幅，三种机型在 15 个服务区的完整最大安全载荷结果见附录表~\\ref{tab:appq1}，
各服务区的组批方案明细见附录表~\\ref{tab:appq1b}，正文只给出关键数值与图示结果。

"""

BATCH_TABLE = """\\begin{table}[H]
\\centering
\\caption{问题一各服务区组批方案明细}
\\label{tab:appq1b}
\\renewcommand\\arraystretch{1.15}
\\begin{tabularx}{\\textwidth}{|C|C|C|C|C|C|}
  \\hline
  服务区 & 架次数/架次 & 机型构成 & 运输能耗/kWh & 累计作业时间/s & 最大安全载荷（C 型）/kg \\\\
  \\hline
BATCHROWS
  \\hline
\\end{tabularx}
\\end{table}

"""


def extract_float(text, caption):
    i = text.find(caption)
    if i == -1:
        raise SystemExit(f"未找到表：{caption}")
    a = text.rfind("\\begin{table}", 0, i)
    b = text.find("\\end{table}", i) + len("\\end{table}")
    return a, b, text[a:b]


def batch_rows():
    with io.open(os.path.join(RESULTS, "q1_results.json"), encoding="utf-8") as fh:
        data = json.load(fh)
    plan = data["组批方案"]["N_E_T"]["per_area"]
    payload = data["最大安全载荷_kg"]
    rows = []
    for area in sorted(plan, key=lambda x: -plan[x]["E"]):
        comp = {}
        for s in plan[area]["plan"]:
            comp[s["type_id"]] = comp.get(s["type_id"], 0) + 1
        comp_s = "、".join(f"{k}×{v}" for k, v in sorted(comp.items()))
        rows.append(f"  {area} & {plan[area]['N']} & {comp_s} & "
                    f"{plan[area]['E']:.3f} & {plan[area]['T']:.1f} & "
                    f"{payload[area]['C']:.2f} \\\\")
    return "\n  \\hline\n".join(rows)


def main() -> int:
    with io.open(MAIN, encoding="utf-8") as fh:
        text = fh.read()

    # --- 取出两张待迁移的表 ---
    a1, b1, payload_float = extract_float(
        text, "三种机型在各服务区的最大安全载荷与满载往返能耗占返航能量上限比例")
    a2, b2, fleet_float = extract_float(text, "中继机队规模对联合调度可行性的影响")
    # 先删后面的，避免位移
    for a, b in sorted(((a1, b1), (a2, b2)), reverse=True):
        text = text[:a] + text[b:]
    payload_float = payload_float.replace("\\label{tab:q1payload}", "\\label{tab:appq1}")
    payload_float = payload_float.replace("\\begin{table}[htbp]", "\\begin{table}[H]", 1)
    fleet_float = fleet_float.replace("\\label{tab:q3fleet}", "\\label{tab:appq3b}")
    fleet_float = fleet_float.replace("\\begin{table}[htbp]", "\\begin{table}[H]", 1)

    # --- 正文改为引用 ---
    text = text.replace(
        "按式~\\eqref{eq:qstar} 对 3 机型与 15 服务区共 45 个组合二分求根，结果如表~\\ref{tab:q1payload} 所示。",
        "按式~\\eqref{eq:qstar} 对 3 机型与 15 服务区共 45 个组合二分求根。"
        "关键结果为：A 型在全部 15 个服务区均达到额定上限 25.00 kg，"
        "B 型除 S008 为 28.63 kg 外均达 30.00 kg，"
        "C 型在 S002、S003、S004、S008、S012 五个服务区受能量约束，最小为 S008 的 58.43 kg。"
        "完整结果见附录表~\\ref{tab:appq1}。")
    text = text.replace(
        "表中占比为满载往返能耗与返航能量上限之比",
        "附录表中占比为满载往返能耗与返航能量上限之比")
    text = text.replace(
        "重算联合调度，结果如表~\\ref{tab:q3fleet} 所示。",
        "重算联合调度，完整结果见附录表~\\ref{tab:appq3b}。")

    # --- 附录 A 与 C 补入迁移表 ---
    text = text.replace("\\section{问题二附录}", APPENDIX_A_HEAD + "\\section{问题二附录}", 1)
    # 在附录 A 的指针段之后插入两张表
    ins = text.find("\\section{问题二附录}")
    text = (text[:ins] + payload_float + "\n\n"
            + BATCH_TABLE.replace("BATCHROWS", batch_rows()) + text[ins:])
    # 附录 C 补入中继机队规模表
    pos = text.find("\\section{问题四附录}")
    text = text[:pos] + fleet_float + "\n\n" + text[pos:]
    # 附录小节改名
    text = text.replace("\\section{问题三附录}", "\\section{问题三附录}", 1)
    text = text.replace("\\section{问题四附录}", "\\section{问题四附录}", 1)

    with io.open(MAIN, "w", encoding="utf-8") as fh:
        fh.write(text)
    print("已迁移 2 张数据表到附录，并新增组批方案明细表")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())