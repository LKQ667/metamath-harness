#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""运行 mathmodel 最小论文链路，产出真实 Draw.io 文件、中文 PDF 与门禁证据。"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SKILL = ROOT / ".dsh" / "skills" / "math-paper-cn"
EVIDENCE = ROOT / "Overall-goal" / "goal-1" / "evidence" / "task-021"
PROJECT = EVIDENCE / "project"
PAPER = PROJECT / "论文"
FIGURES = PROJECT / "figures"
REPORTS = PROJECT / "检查结果"
DRAWIO_PIPELINE = SKILL / "scripts" / "drawing" / "drawio_pipeline.py"
LATEX_RUNTIME = SKILL / "scripts" / "latex" / "latex_runtime.py"
CHECKS = SKILL / "scripts" / "checks"


def run(command: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        command,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=1800,
    )
    if proc.returncode:
        raise RuntimeError(f"命令失败（{proc.returncode}）：{' '.join(command)}\n{proc.stdout[-4000:]}")
    return proc


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def tex_source() -> str:
    topics = [
        ("问题重述与目标", "把原始赛题拆分为数据、状态、决策和评价四类对象，明确每个子问题的输入输出关系。"),
        ("数据审计", "检查字段口径、缺失机制、异常值来源与时间粒度，所有变换均保留可追溯记录。"),
        ("符号与假设", "仅保留可验证且会进入公式的假设，并说明适用边界和可能造成的方向性偏差。"),
        ("基准模型", "先建立可解释基准，再用复杂模型比较增益，避免把算法复杂度误当作结论可靠性。"),
        ("约束系统", "将资源、容量、时序和业务规则写成显式约束，逐项检查量纲与可行域。"),
        ("目标函数", "目标函数同时表达效果、成本和风险，并通过权重敏感性解释偏好变化。"),
        ("求解流程", "记录初始化、停止条件、随机种子和收敛判据，使计算路径能够独立复核。"),
        ("参数估计", "区分训练信息与验证信息，用区间和误差而非单点数字表达参数不确定性。"),
        ("结果验证", "通过留出验证、边界样例和守恒关系共同检验，避免仅凭拟合优度判断。"),
        ("敏感性分析", "逐项扰动关键参数，观察结论排序和约束活跃状态是否发生结构性改变。"),
        ("稳健性检验", "在数据噪声、参数漂移和情景变化下重复求解，报告稳定区间与失效条件。"),
        ("误差解释", "将误差拆为测量、抽样、模型设定和数值求解四类，分别讨论传播方向。"),
        ("方案比较", "采用统一指标比较候选方案，保留不可比因素并说明最终取舍依据。"),
        ("结论回扣", "每条结论明确对应子问题、证据文件和适用条件，不外推到未覆盖场景。"),
        ("复现清单", "核对数据、代码、图片源文件、参数与环境版本，形成从输入到结论的证据链。"),
    ]
    pages = []
    for index, (title, prose) in enumerate(topics, 2):
        pages.append(
            rf"""\clearpage
\section{{{index - 1}. {title}}}
{prose}

本页用于验证一键论文链路的真实中文排版与页码边界。设观测向量为 $x$，决策向量为 $z$，
统一评价函数写为
\[
J(z)=\alpha L(z;x)+\beta C(z)+\gamma R(z),\qquad \alpha+\beta+\gamma=1.
\]
验收时检查公式、中文字体、交叉引用与文件哈希。该夹具不声称解决具体赛题，只验证工具链是否能够
稳定地产生可编辑流程图、可编译论文和机器可读门禁报告。
"""
        )
    return rf"""\documentclass[12pt,a4paper]{{ctexart}}
\usepackage[margin=2.5cm]{{geometry}}
\usepackage{{graphicx}}
\usepackage{{amsmath}}
\usepackage{{appendix}}
\newcommand{{\titlefont}}{{\bfseries\LARGE}}
\newcommand{{\sectiontitlefont}}{{\bfseries\large}}
\setlength{{\parindent}}{{2em}}
\begin{{document}}
\label{{body:start}}
{{\titlefont DeepSeek Harness 数学建模一键链路验收报告}}

{{\sectiontitlefont 摘要}}

本文构造一个不依赖外部赛题数据的最小验收夹具，依次验证卡片锁定的“禁用普通柱状图”策略、
Draw.io 可编辑源文件及三种真实导出、中文 XeLaTeX 编译和正文页数硬门禁。所有结论均来自本次运行产物，
不把测试报告包装成学术研究结果。

\textbf{{关键词：}}数学建模；端到端验收；可编辑流程图；中文排版；证据链

\section{{技术路线}}
\begin{{center}}
\includegraphics[width=0.94\textwidth]{{../figures/roadmap.png}}
\end{{center}}
图中中文节点来自 Draw.io 源文件，PNG、SVG 与 PDF 均由桌面 CLI 在本次运行中导出。
{''.join(pages)}
\begin{{thebibliography}}{{9}}
\bibitem{{fixture}} DeepSeek Harness，数学建模模式端到端验收夹具，2026。
\end{{thebibliography}}
\label{{body:end}}
\clearpage
\label{{appendix:start}}
\begin{{appendices}}
\section{{支撑材料文件目录}}
流程图源文件、三种导出、图片清单、页数与柱状图策略报告均位于本夹具目录。
\section{{附录代码文件}}
执行入口为 \texttt{{npm run e2e:paper}}，报告记录真实命令、文件大小与 SHA-256。
\end{{appendices}}
\end{{document}}
"""


def main() -> int:
    for directory in (PAPER, FIGURES, REPORTS):
        directory.mkdir(parents=True, exist_ok=True)

    source = FIGURES / "roadmap.drawio"
    labels_path = FIGURES / "roadmap-labels.json"
    labels_path.write_text(
        json.dumps(
            {"n1": "赛题与数据", "n2": "假设与变量", "n3": "模型与约束", "n4": "求解与验证", "n5": "结论与交付"},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    run([sys.executable, str(DRAWIO_PIPELINE), "build", "--template", "horizontal-stage-chain", "--output", str(source), "--labels-json", str(labels_path)])
    run([sys.executable, str(DRAWIO_PIPELINE), "export", str(source), "--output-dir", str(FIGURES)])

    manifest = {
        "bar_chart_policy": "禁用",
        "items": [{
            "id": "roadmap",
            "title": "数学建模技术路线",
            "generator": "drawio",
            "chart_family": "flowchart",
            "source": "figures/roadmap.drawio",
            "exports": ["figures/roadmap.png", "figures/roadmap.svg", "figures/roadmap.pdf"],
        }],
    }
    (FIGURES / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (PAPER / "main.tex").write_text(tex_source(), encoding="utf-8", newline="\n")

    latex_report = REPORTS / "latex-compile.json"
    run([sys.executable, str(LATEX_RUNTIME), "compile", "--project", str(PROJECT), "--tex", str(PAPER / "main.tex"), "--output", str(latex_report)])
    body_report = REPORTS / "body-page-count.json"
    run([sys.executable, str(CHECKS / "check_body_page_count_minimum.py"), "--project", str(PROJECT), "--output", str(body_report)])
    bar_report = REPORTS / "bar-chart-policy.json"
    run([sys.executable, str(CHECKS / "check_python_bar_chart_policy.py"), "--project", str(PROJECT), "--output", str(bar_report)])

    pdf = PAPER / "main.pdf"
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("缺少 pypdf，无法独立核验 PDF 页数") from exc
    total_pages = len(PdfReader(str(pdf)).pages)

    artifacts = [source, FIGURES / "roadmap.png", FIGURES / "roadmap.svg", FIGURES / "roadmap.pdf", pdf]
    checks = {
        "drawio_source_valid": source.stat().st_size > 500,
        "drawio_exports_real": all(path.exists() and path.stat().st_size > 500 for path in artifacts[1:4]),
        "chinese_pdf_real": pdf.exists() and pdf.stat().st_size > 10_000,
        "body_page_gate": json.loads(body_report.read_text(encoding="utf-8"))["ok"],
        "bar_policy_gate": json.loads(bar_report.read_text(encoding="utf-8"))["ok"],
        "bar_policy_locked_disabled": manifest["bar_chart_policy"] == "禁用",
        "pdf_total_pages_at_least_17": total_pages >= 17,
    }
    report = {
        "schema": "dsh.mathmodel.paper-e2e/v1",
        "ok": all(checks.values()),
        "checks": checks,
        "pdf_total_pages": total_pages,
        "artifacts": [
            {"path": str(path.relative_to(ROOT)).replace("\\", "/"), "bytes": path.stat().st_size, "sha256": sha256(path)}
            for path in artifacts
        ],
        "gate_reports": [str(path.relative_to(ROOT)).replace("\\", "/") for path in (latex_report, body_report, bar_report)],
    }
    acceptance = EVIDENCE / "acceptance-report.json"
    acceptance.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
