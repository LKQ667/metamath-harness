"""验证 Draw.io 桌面端 CLI 可用性并写出可追溯记录。

运行时清理继承的 Node 运行时环境变量并追加无沙箱参数，使 Electron 正常解析导出参数。
记录写入 检查结果/drawio_cli_verification.json。
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = PROJECT_ROOT / "检查结果" / "drawio_cli_verification.json"
WORK_DIR = PROJECT_ROOT / "检查结果" / "_drawio_cli_check"
EXTRA_ARGS = ["--no-sandbox", "--disable-gpu"]


def skill_drawing_dir() -> Path:
    import sys

    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
    from plot_common import skill_root

    return skill_root() / "scripts" / "drawing"


def find_drawio() -> Path | None:
    candidates = [os.environ.get("DRAWIO_CLI"), shutil.which("drawio"), shutil.which("draw.io")]
    program_files = os.environ.get("ProgramFiles")
    if program_files:
        candidates.append(str(Path(program_files) / "draw.io" / "draw.io.exe"))
    program_files_x86 = os.environ.get("ProgramFiles(x86)")
    if program_files_x86:
        candidates.append(str(Path(program_files_x86) / "draw.io" / "draw.io.exe"))
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate)
    return None


def clean_env() -> dict:
    env = dict(os.environ)
    env.pop("NODE_OPTIONS", None)
    env.pop("ELECTRON_RUN_AS_NODE", None)
    return env


def run(executable: Path, args: list[str], timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(executable), *EXTRA_ARGS, *args],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=timeout,
        env=clean_env(),
    )


def wait_stable(path: Path, timeout: float = 40.0) -> bool:
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
    import sys

    sys.path.insert(0, str(skill_drawing_dir()))
    from drawio_pipeline import build_xml, validate_drawio  # noqa: PLC0415

    WORK_DIR.mkdir(parents=True, exist_ok=True)
    source = WORK_DIR / "中文最小验证.drawio"
    source.write_text(build_xml("horizontal-stage-chain", {"n1": "中文字体验证"}), encoding="utf-8")

    executable = find_drawio()
    if executable is None:
        record = {"ok": False, "error": "drawio_cli_missing"}
        OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUT_PATH.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(record, ensure_ascii=False))
        return

    record = {
        "executable": str(executable.resolve()),
        "executable_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
        "version": "",
        "version_ok": False,
        "source_ok": not validate_drawio(source),
        "cn_text_ok": False,
        "exports": {},
        "sandbox_args": EXTRA_ARGS,
        "node_options_cleared": True,
    }
    version = run(executable, ["--version"], timeout=60)
    text = (version.stdout.strip() or version.stderr.strip())
    record["version"] = text.splitlines()[0].strip() if text else ""
    record["version_ok"] = version.returncode == 0 and bool(record["version"])

    for fmt in ("png", "svg", "pdf"):
        output = WORK_DIR / f"中文最小验证.{fmt}"
        args = ["--export", "--format", fmt]
        if fmt == "png":
            args += ["--scale", "2"]
        args += ["--output", str(output), str(source)]
        proc = run(executable, args)
        record["exports"][fmt] = bool(proc.returncode == 0 and wait_stable(output))

    svg_path = WORK_DIR / "中文最小验证.svg"
    if svg_path.exists():
        svg_text = svg_path.read_text(encoding="utf-8", errors="ignore")
        record["cn_text_ok"] = ("中文字体验证" in svg_text) or ("Microsoft YaHei" in svg_text)

    record["ok"] = all(
        [record["version_ok"], record["source_ok"], record["cn_text_ok"], *record["exports"].values()]
    )
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False))


if __name__ == "__main__":
    main()
