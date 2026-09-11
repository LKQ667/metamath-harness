"""生成技术路线图（Draw.io）：原子选择模板、构建源文件并导出 PNG/SVG/PDF。

模板由内置模板库按图稿摘要自动选路，labels 只做中文化覆盖，禁止手写 XML。
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from plot_common import skill_root  # noqa: E402

HAND_DIR = PROJECT_ROOT / "手绘图"
NAME = "技术路线图"
EXTRA_ARGS = ["--no-sandbox", "--disable-gpu"]

BRIEF = {
    "kind": "roadmap",
    "output_banner": 1,
    "panels": 0,
    "side_head": 0,
    "feedback": 0,
    "branches": 0,
    "actors": 1,
    "support_blocks": 0,
    "focus_stage": 0,
    "stages": 4,
    "direction": "vertical",
}

LABELS = {
    "step1_title": "步骤一  数据与工况准备",
    "step1_box1_title": "烘房工况数据",
    "step1_box1_text": "<b>输入：</b><br>附件 1 共 241 条<br>温度 28.000—50.165 ℃<br>水分浓度 0.0196—0.0499 kg/kg",
    "equest_logo_q": "1",
    "equest_logo_label": "附件 1",
    "step1_box2_title": "药材几何与收缩数据",
    "step1_box2_text": "<b>输入：</b><br>附件 2 共 145 条<br>半径 2.000—1.198 cm<br>覆盖 0—72 h",
    "sam_logo_sun": "2",
    "sam_logo_label": "附件 2",
    "step1_box3_title": "初始条件与参数",
    "sys_pv": "28 ℃",
    "sys_wt": "2.55",
    "sys_batt": "常数物性",
    "sys_hp": "附录 3",
    "sys_inv": "附录 4",
    "sys_boiler": "h",
    "sys_chiller": "h_m",
    "sys_grid": "边界",
    "sys_load_cool": "温度",
    "sys_load_heat": "含水率",
    "sys_load_elec": "时长",
    "sys_lbl": "输入条件",
    "step1_bottom_box1": "• 附件 1 提供预热平衡与恒温干燥工况",
    "step1_bottom_box2": "• 附件 2 提供失水收缩实测半径",
    "step1_bottom_box3": "<font color=\"#B60000\">• 附件 3 提供四份结果模板</font>",
    "step2_title": "步骤二  数据预处理与参数设定",
    "step2_box1_title": "工况序列规整",
    "step2_l_lbl45": "50",
    "step2_l_lbl30": "40",
    "step2_l_lbl15": "34",
    "step2_l_lbl0": "28",
    "step2_l_xlbl": "",
    "step2_r_lbl45": "0.05",
    "step2_r_lbl30": "0.04",
    "step2_r_lbl15": "0.03",
    "step2_r_lbl0": "0.02",
    "step2_r_xlbl": "",
    "step2_box1_redlabel": "温度与水分浓度同步上升，相关系数 0.983",
    "step2_box2_title": "参数设定",
    "step2_box2_text": "<b>物性经验式：</b>密度、比热容与导热系数随含水率单调增大<br><br><b>扩散系数：</b>随含水率指数衰减、随温度升高而增大<br><br><b>网格与步长：</b>径向 0.01 cm，时间 1—10 s",
    "step3_title": "步骤三  模型建立",
    "step3_box1_title": "控制方程",
    "step3_box1_val": "含水率扩散方程<br>温度导热方程",
    "step3_box2_title": "边界条件",
    "step3_box2_val": "第三类边界<br>对流换热与对流传质",
    "step3_box3_title": "求解方法",
    "step3_box3_val": "节点中心有限体积<br>后向 Euler 隐式推进",
    "step3_box4_title": "移动边界",
    "step3_box4_val": "收缩坐标变换<br>ξ = r / R(t)",
    "step4_title": "步骤四  数值求解与结果分析",
    "step4_box1_title": "计算工具",
    "matlab_logo_label": "Python<br>数值求解",
    "matlab_gurobi_plus": "+",
    "gurobi_logo_label": "SciPy<br>三对角求解",
    "step4_box2_title": "结果输出",
    "step4_box2_formula": "<b>温度场与含水率场</b><br>四份结果工作簿<br>烘干时长 57.1 h / 50.8 h",
    "step4_box2_redlabel": "全断面含水率低于 0.15 kg/kg",
    "step4_box3_title": "分析与校核",
    "origin_logo_label": "灵敏度分析<br>网格与步长无关性",
    "palette_orange_lbl": "边界工况",
    "palette_darkgray_lbl": "求解方法",
    "palette_green_lbl": "结果输出",
    "palette_lightblue_lbl": "数据输入",
    "palette_blue_lbl": "模型方程",
    "palette_darkerblue_lbl": "交付指标",
}


def clean_env() -> dict:
    env = dict(os.environ)
    env.pop("NODE_OPTIONS", None)
    env.pop("ELECTRON_RUN_AS_NODE", None)
    return env


def find_drawio() -> Path | None:
    import shutil

    candidates = [os.environ.get("DRAWIO_CLI"), shutil.which("drawio"), shutil.which("draw.io")]
    for key in ("ProgramFiles", "ProgramFiles(x86)"):
        base = os.environ.get(key)
        if base:
            candidates.append(str(Path(base) / "draw.io" / "draw.io.exe"))
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate)
    return None


def wait_stable(path: Path, timeout: float = 45.0) -> bool:
    deadline = time.monotonic() + timeout
    last = None
    stable = 0
    while time.monotonic() < deadline:
        size = path.stat().st_size if path.exists() else 0
        if size > 0 and size == last:
            stable += 1
            if stable >= 2:
                return True
        else:
            stable = 0
        last = size
        time.sleep(0.25)
    return False


def main() -> None:
    drawing_dir = skill_root() / "scripts" / "drawing"
    sys.path.insert(0, str(drawing_dir))
    from drawio_pipeline import build_xml, choose_template, template_structure_errors, validate_drawio  # noqa: PLC0415

    HAND_DIR.mkdir(parents=True, exist_ok=True)
    template_id = choose_template(BRIEF)
    source = HAND_DIR / f"{NAME}.drawio"
    source.write_text(build_xml(template_id, LABELS), encoding="utf-8")

    errors = validate_drawio(source, template_id)
    errors.extend(template_structure_errors(source, template_id))
    if errors:
        print(json.dumps({"ok": False, "template_id": template_id, "errors": errors}, ensure_ascii=False))
        raise SystemExit(1)

    executable = find_drawio()
    if executable is None:
        print(json.dumps({"ok": False, "error": "drawio_cli_missing"}, ensure_ascii=False))
        raise SystemExit(1)

    exports: dict[str, str] = {}
    for fmt in ("png", "svg", "pdf"):
        output = HAND_DIR / f"{NAME}.{fmt}"
        args = ["--export", "--format", fmt]
        if fmt == "png":
            args += ["--scale", "2"]
        args += ["--output", str(output), str(source)]
        proc = subprocess.run(
            [str(executable), *EXTRA_ARGS, *args],
            text=True, encoding="utf-8", errors="replace", capture_output=True,
            timeout=180, env=clean_env(),
        )
        if proc.returncode != 0 or not wait_stable(output):
            print(json.dumps({"ok": False, "format": fmt, "stderr": proc.stderr[-400:]}, ensure_ascii=False))
            raise SystemExit(1)
        exports[fmt] = str(output.relative_to(PROJECT_ROOT)).replace("\\", "/")

    print(
        json.dumps(
            {
                "ok": True,
                "template_id": template_id,
                "source": str(source.relative_to(PROJECT_ROOT)).replace("\\", "/"),
                "exports": exports,
                "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
