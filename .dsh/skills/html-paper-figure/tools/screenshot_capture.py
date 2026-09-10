#!/usr/bin/env python3
"""HTML 截图/出 PDF 命令行包装器 — paper-figure-html skill 用（MetaMath Harness/DSH 适配版）。

底层调用同目录 capture.js（Electron printToPDF）：
  electron capture.js --mh-capture <config.json>

用法（与原 MH Agent 发行版 screenshot_capture.py 完全兼容）:
  python screenshot_capture.py --check                                  # 只探测 Electron 是否可用(0=可用 2=不可用)
  python screenshot_capture.py --url http://127.0.0.1:19001/ --out figures/shot_home.png
  python screenshot_capture.py --file figures/fig_roadmap.html --out figures/fig_roadmap.pdf --format pdf
  python screenshot_capture.py --file figures/fig_flow_q1.html --out figures/fig_flow_q1.pdf --format pdf --render-math
  python screenshot_capture.py --geom-check figures/fig_flow_q1.html            # 只测几何不出图
  python screenshot_capture.py --geom-check figures/fig_flow_q1.html --render-math
  python screenshot_capture.py --config shots.json

说明:
  --format pdf（或 out 以 .pdf 结尾）→ Electron printToPDF 出「矢量单页无白边」PDF，供 LaTeX \\includegraphics。
  --render-math → 截图前注入 KaTeX 渲染 \\(...\\)/\\[...\\]/$$（素材在同目录 katex-assets/，缺失自动降级）。
  --geom-check → 元素级几何自检（文字溢出/越界/重叠/对齐偏差），只测量不出图。

退出码:
  0 = 全部成功 / 几何自检干净
  1 = 有失败 / 几何自检发现问题（打印明细，skill 端据此修复重出）
  2 = Electron 不可用（找不到运行时；skill 端跳过或报告用户）
  3 = 参数/致命错误

Electron 定位顺序（与原版一致 + DSH 适配）:
  1) 环境变量 MH_ELECTRON_EXE / RUNTIME_ELECTRON_EXE（可指向 electron 可执行文件或打包 app 主程序）
  2) PATH 上的 electron 命令
  3) npx --yes electron（首次会下载到 npm 缓存，之后秒启）
capture.js 定位：优先 MH_ELECTRON_MAIN / RUNTIME_ELECTRON_MAIN 同目录，其次本脚本同目录。

⛔ 纯标准库实现，无第三方依赖。Windows 控制台 GBK 已做 UTF-8 重编码兜底。
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Windows 控制台默认 GBK，打印 ℹ/⚠/❌ 等符号会 UnicodeEncodeError。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_THIS_DIR = Path(__file__).resolve().parent
_CAPTURE_JS = _THIS_DIR / "capture.js"
_TIMEOUT_S = 300  # 首次 npx 下载 electron 较慢，给足时间


def _resolve_electron() -> tuple[list[str] | None, str]:
    """返回 (命令列表, 描述)。找不到返回 (None, 原因)。"""
    # 1) 环境变量（可执行文件）
    for var in ("MH_ELECTRON_EXE", "RUNTIME_ELECTRON_EXE"):
        exe = os.environ.get(var)
        if exe and Path(exe).exists():
            return [exe], f"env:{var}"
    # 2) PATH 上的 electron
    which = shutil.which("electron")
    if which:
        return [which], "PATH"
    # 3) npx --yes electron（Windows 上是 npx.cmd）
    npx = shutil.which("npx") or shutil.which("npx.cmd")
    if npx:
        return [npx, "--yes", "electron"], "npx"
    return None, "未找到 electron（PATH/npx 均不可用，也未设置 MH_ELECTRON_EXE）"


def _resolve_capture_js() -> Path | None:
    """capture.js 定位：环境变量指定的 main 同目录 → 本脚本同目录。"""
    for var in ("MH_ELECTRON_MAIN", "RUNTIME_ELECTRON_MAIN"):
        main = os.environ.get(var)
        if main:
            cand = Path(main).resolve().parent / "capture.js"
            if cand.exists():
                return cand
    if _CAPTURE_JS.exists():
        return _CAPTURE_JS
    return None


def _run_capture(targets: list[dict], viewport: dict | None = None) -> tuple[int, dict | None]:
    """调 electron capture.js --mh-capture cfg.json，返回 (退出码, result dict)。"""
    electron_cmd, reason = _resolve_electron()
    cap_js = _resolve_capture_js()
    if electron_cmd is None:
        print(f"❌ Electron 不可用：{reason}", file=sys.stderr)
        return 2, None
    if cap_js is None:
        print("❌ capture.js 不可用（应与本脚本同目录）", file=sys.stderr)
        return 2, None

    cap_js = cap_js.resolve()
    with tempfile.TemporaryDirectory(prefix="mh_capture_") as tmp:
        cfg_path = Path(tmp) / "cfg.json"
        result_path = Path(tmp) / "result.json"
        cfg: dict = {"targets": targets, "resultPath": str(result_path)}
        if viewport:
            cfg["viewport"] = viewport
        cfg_path.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")

        cmd = electron_cmd + [str(cap_js), "--mh-capture", str(cfg_path)]
        env = dict(os.environ)
        env["ELECTRON_DISABLE_SECURITY_WARNINGS"] = "1"
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=_TIMEOUT_S,
                encoding="utf-8", errors="replace", env=env,
            )
        except subprocess.TimeoutExpired:
            print(f"❌ Electron 截图超时（>{_TIMEOUT_S}s）", file=sys.stderr)
            return 1, None
        except Exception as e:
            print(f"❌ spawn 失败: {e}", file=sys.stderr)
            return 2, None

        if proc.stdout:
            print(proc.stdout.rstrip())
        if proc.stderr:
            print(proc.stderr.rstrip(), file=sys.stderr)

        result = None
        if result_path.exists():
            try:
                result = json.loads(result_path.read_text(encoding="utf-8"))
            except Exception:
                result = None

    if proc.returncode == 3:
        return 3, result
    ok = bool(result and result.get("results")) and all(
        r.get("ok") for r in result["results"]
    )
    return (0 if ok else 1), result


# ===== 几何自检报告（人类可读明细，照 SKILL.md 的口径打印）=====

def _fmt_geom_report(geom: dict) -> tuple[int, str]:
    """返回 (退出码, 报告文本)。0=干净 1=有问题 2=无法检查。"""
    if not isinstance(geom, dict):
        return 2, "geom_probe_failed: 返回值非对象 — 跳过"
    if geom.get("error"):
        return 2, f"geom_probe_failed: {geom['error']} — 跳过"

    fig = geom.get("fig") or {}
    overflow = geom.get("overflow") or []
    clip = geom.get("clip") or []
    overlap = geom.get("overlap") or []
    misalign = geom.get("misalign") or []

    lines = [
        f"=== geom-check: .fig {fig.get('w','?')}x{fig.get('h','?')}px, "
        f"{geom.get('blocks', '?')} 个文字块 ===",
        f"  溢出 {len(overflow)} | 越界 {len(clip)} | 重叠 {len(overlap)} | 对齐偏差 {len(misalign)}",
    ]
    for o in overflow:
        lines.append(
            f"  ❌ 溢出被裁: 「{o.get('txt','')}」 内容 {o.get('sw')}x{o.get('sh')}px"
            f" > 盒 {o.get('cw')}x{o.get('ch')}px → 加宽/缩字/允许换行"
        )
    for c in clip:
        edges = []
        for k, lab in (("left", "左"), ("top", "上"), ("right", "右"), ("bottom", "下")):
            if c.get(k, 0) > 0:
                edges.append(f"{lab}{c[k]}px")
        lines.append(
            f"  ❌ 越出 .fig 边界: 「{c.get('txt','')}」 {('、'.join(edges)) or '越界'}"
            f" → 回 flex/grid 文档流，去绝对定位"
        )
    for ov in overlap:
        lines.append(
            f"  ❌ 文字块重叠: 「{ov.get('a','')}」×「{ov.get('b','')}」"
            f" 交叠约 {ov.get('area',0)}px² → 拆 flex 轨道/加 gap"
        )
    for m in misalign:
        members = "、".join(m.get("members") or [])
        axis_desc = "中轴 x" if m.get("axis") == "x" else "中轴 y"
        lines.append(
            f"  ❌ 对齐偏差: {m.get('attr')}=\"{m.get('group')}\" 组（{m.get('count')} 个成员）"
            f"{axis_desc} 极差 {m.get('spread')}px > 4px → 同组装进同一 grid 拉齐"
            f"（成员: {members}）"
        )
    if not (overflow or clip or overlap or misalign):
        lines.append("  ✅ 几何干净：无溢出/越界/重叠/对齐偏差")
        return 0, "\n".join(lines)
    return 1, "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="HTML 截图/出矢量 PDF（Electron printToPDF）+ 元素级几何自检"
    )
    ap.add_argument("--url", help="待截图的 http(s) URL")
    ap.add_argument("--file", help="待截图的本地 HTML 文件")
    ap.add_argument("--out", help="输出路径（.png 截图 / .pdf 矢量）")
    ap.add_argument("--format", choices=["png", "pdf"], default=None,
                    help="输出格式（缺省按 out 后缀推断）")
    ap.add_argument("--render-math", action="store_true",
                    help="截图前注入 KaTeX 渲染公式")
    ap.add_argument("--geom-check", metavar="HTML",
                    help="只做元素级几何自检（不出图）")
    ap.add_argument("--check", action="store_true",
                    help="只探测 Electron 是否可用（0=可用 2=不可用）")
    ap.add_argument("--config", help="批量配置 JSON（targets 数组）")
    ap.add_argument("--wait-ms", type=int, default=None, help="加载后额外等待(毫秒)")
    ap.add_argument("--wait-for-selector", default=None, help="等某元素出现再截")
    ap.add_argument("--full-page", action="store_true", help="(仅 png)整页截图")
    ap.add_argument("--viewport", default=None, help="视口尺寸，如 1280x800")
    args = ap.parse_args()

    if args.check:
        electron_cmd, reason = _resolve_electron()
        cap_js = _resolve_capture_js()
        if electron_cmd is None:
            print(f"ELECTRON_UNAVAILABLE: {reason}", file=sys.stderr)
            sys.exit(2)
        if cap_js is None:
            print("CAPTURE_JS_UNAVAILABLE: capture.js 不在本脚本同目录", file=sys.stderr)
            sys.exit(2)
        print(f"Electron 可用（{reason}）；capture.js: {cap_js}")
        sys.exit(0)

    viewport = None
    if args.viewport:
        try:
            w, h = args.viewport.lower().split("x")
            viewport = {"width": int(w), "height": int(h)}
        except Exception:
            print("❌ --viewport 格式应为 宽x高，如 1280x800", file=sys.stderr)
            sys.exit(3)

    # ---- 几何自检（只测量不出图）----
    if args.geom_check:
        html = Path(args.geom_check)
        if not html.exists():
            print(f"NO_FILE: {html} 不存在 — skip", file=sys.stderr)
            sys.exit(2)
        target = {"file": str(html.resolve()), "geomCheck": True}
        if args.render_math:
            target["renderMath"] = True
        code, result = _run_capture([target], viewport)
        if code == 2:
            print("ELECTRON_UNAVAILABLE: 几何自检跳过（不阻塞）", file=sys.stderr)
            sys.exit(2)
        geom = None
        if result and result.get("results"):
            geom = result["results"][0].get("geom")
        if geom is None:
            if code == 1:
                print("❌ 几何自检失败（页面加载/执行出错）", file=sys.stderr)
                sys.exit(1)
            print("GEOM_CHECK_UNAVAILABLE: 未取到几何报告 — 跳过", file=sys.stderr)
            sys.exit(2)
        exit_code, report = _fmt_geom_report(geom)
        print(report)
        sys.exit(exit_code)

    # ---- 批量 config 模式 ----
    if args.config:
        cfg_path = Path(args.config)
        if not cfg_path.exists():
            print(f"NO_FILE: {cfg_path} 不存在", file=sys.stderr)
            sys.exit(3)
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"BAD_CONFIG: {e}", file=sys.stderr)
            sys.exit(3)
        targets = cfg.get("targets") or []
        if not targets:
            print("BAD_CONFIG: targets 为空", file=sys.stderr)
            sys.exit(3)
        code, _ = _run_capture(
            targets, cfg.get("viewport") or viewport
        )
        sys.exit(code)

    # ---- 单目标模式 ----
    if not (args.url or args.file):
        print("❌ 需要 --url/--file/--geom-check/--config/--check 之一", file=sys.stderr)
        sys.exit(3)
    if not args.out:
        print("❌ 单目标模式需要 --out", file=sys.stderr)
        sys.exit(3)

    target: dict = {"out": args.out}
    if args.url:
        target["url"] = args.url
    else:
        f = Path(args.file)
        if not f.exists():
            print(f"NO_FILE: {f} 不存在", file=sys.stderr)
            sys.exit(3)
        target["file"] = str(f.resolve())
    if args.format:
        target["format"] = args.format
    if args.render_math:
        target["renderMath"] = True
    if args.wait_ms is not None:
        target["waitMs"] = args.wait_ms
    if args.wait_for_selector:
        target["waitForSelector"] = args.wait_for_selector
    if args.full_page:
        target["fullPage"] = True

    code, _ = _run_capture([target], viewport)
    sys.exit(code)


if __name__ == "__main__":
    main()
