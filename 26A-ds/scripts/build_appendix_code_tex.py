"""把附录净化代码内联成 LaTeX 片段。

读取 `检查结果/附录代码复核.json` 中登记的净化副本，按登记顺序生成
`论文/附录代码.tex`：每个文件一个小节、一段功能说明，随后是模板原生 Python
代码环境内联的纯代码。代码块内不出现任何 Markdown 符号、注释或装饰线。
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "检查结果" / "附录代码复核.json"
OUT = ROOT / "论文" / "附录代码.tex"

DESCRIPTIONS = {
    "graph_utils.py": "计算图读取与操作级有向无环图收缩：把 Op-Tensor 二部图合并为操作级依赖，跳过搬运节点，并提供拓扑排序、最长路径与结构统计。",
    "partition.py": "多核切图与子图调度主算法：依赖锥聚簇、连续段切分、分层切分三类无环构造，关键路径优先级分核，以及子图层面的完工时间估算与单核兜底。",
    "eval_runner.py": "赛题官方评估程序的调用封装：统一定位官方脚本、固定配置与测试用例，按问题编号运行评估并把结果写回项目工作目录。",
    "run_experiments.py": "全用例实验总控：按问题与核数矩阵批量生成方案、调用官方评估、缓存中间结果并聚合输出。",
    "aggregate_results.py": "唯一结果源聚合：把逐用例评估输出汇总为平均加速比、平均 Makespan、额外搬运量与 Cache 指标，并复算估算完工时间。",
    "build_dataset.py": "数据预处理入口：解析全部测试用例，输出结构画像 CSV 与处理审计记录。",
    "appendix_regression.py": "附录代码等价性回归入口：在原版与净化副本中执行同一段确定性计算并输出可比对的结构化结果。",
}


def main():
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    entries = config["files"]
    lines = ["% 本文件由 scripts/build_appendix_code_tex.py 生成，内容为净化后的等价代码副本。", ""]
    for index, entry in enumerate(entries, 1):
        name = Path(entry["appendix"]).name
        path = ROOT / entry["appendix"]
        if not path.exists():
            raise FileNotFoundError(f"缺少附录净化文件: {entry['appendix']}")
        code = path.read_text(encoding="utf-8").rstrip("\n")
        title = name.replace("_", "\\_")
        lines.append(f"\\subsection{{{title}}}")
        lines.append("")
        lines.append(DESCRIPTIONS.get(name, "本文件为论文建模链路的核心代码，内联其等价净化副本。"))
        lines.append("")
        lines.append(f"% 附录代码来源：{entry['appendix']}")
        lines.append(f"\\begin{{Python}}{{{title}}}")
        lines.append(code)
        lines.append("\\end{Python}")
        lines.append("")
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"ok": True, "files": len(entries), "out": str(OUT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
