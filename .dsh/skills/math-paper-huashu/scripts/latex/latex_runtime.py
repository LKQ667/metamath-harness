#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Windows LaTeX 运行时探测、自举、诊断与编译。"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


SKILL_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = SKILL_ROOT / "assets" / "latex" / "runtime-manifest.json"
PROFILE_PATH = SKILL_ROOT / "assets" / "latex" / "texlive.profile"
RUNTIME_ENV = "MATH_PAPER_CN_RUNTIME"
PORTABLE_RUNTIME_ENV = "DSH_RUNTIME_ROOT"
PORTABLE_STRICT_ENV = "DSH_PORTABLE_STRICT"
PORTABLE_ALIAS_ENV = "DSH_PORTABLE_ALIAS_DRIVE"
OFFLINE_ENV = "MATH_PAPER_CN_TEXLIVE_OFFLINE"
ASCII_RE = re.compile(r"^[\x00-\x7f]+$")
MISSING_FILE_RE = re.compile(r"(?:File [`']([^`']+\.(?:sty|cls))['`] not found|LaTeX Error: File [`']([^`']+)['`] not found)")


class LatexRuntimeError(RuntimeError):
    """可恢复或不可恢复的 LaTeX 运行时错误。"""


@dataclass(frozen=True)
class Toolchain:
    source: str
    xelatex: Path
    latexmk: Path
    tlmgr: Path | None = None
    root: Path | None = None

    def as_dict(self) -> dict[str, str | None]:
        return {
            "source": self.source,
            "xelatex": str(self.xelatex),
            "latexmk": str(self.latexmk),
            "tlmgr": str(self.tlmgr) if self.tlmgr else None,
            "root": str(self.root) if self.root else None,
        }


def load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def is_windows() -> bool:
    return os.name == "nt"


def process_path(path: Path) -> Path:
    """TeX Live Windows 脚本在非 ASCII 根目录下需通过 8.3 短路径启动。"""
    if not is_windows() or is_ascii_path(path):
        return path
    buffer = ctypes.create_unicode_buffer(32768)
    if ctypes.windll.kernel32.GetShortPathNameW(str(path), buffer, len(buffer)):
        return Path(buffer.value)
    return path


def is_ascii_path(path: Path) -> bool:
    return bool(ASCII_RE.fullmatch(str(path)))


def is_inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def fixed_drives() -> list[Path]:
    if not is_windows():
        return []
    drives: list[Path] = []
    bitmask = ctypes.windll.kernel32.GetLogicalDrives()
    for index in range(26):
        if not bitmask & (1 << index):
            continue
        root = Path(f"{chr(65 + index)}:\\")
        if ctypes.windll.kernel32.GetDriveTypeW(str(root)) == 3:
            drives.append(root)
    return drives


def existing_parent(path: Path) -> Path:
    current = path
    while not current.exists() and current != current.parent:
        current = current.parent
    return current


def choose_runtime_root(
    project: Path,
    minimum_free_bytes: int | None = None,
    create: bool = True,
) -> Path:
    """选择项目外、优先非 C 盘且仅含 ASCII 的运行时目录。"""
    manifest = load_manifest()
    required = minimum_free_bytes or int(manifest["minimum_free_bytes"])
    override = os.environ.get(PORTABLE_RUNTIME_ENV) or os.environ.get(RUNTIME_ENV)
    if override:
        candidate = Path(override).expanduser()
        if os.environ.get(PORTABLE_RUNTIME_ENV) and candidate.name.lower() != "texlive":
            candidate /= "texlive"
        if not is_ascii_path(candidate):
            raise LatexRuntimeError(f"{RUNTIME_ENV} 必须是纯 ASCII 路径: {candidate}")
        if is_inside(candidate, project):
            raise LatexRuntimeError(f"{RUNTIME_ENV} 不能位于项目交付目录内: {candidate}")
        parent = existing_parent(candidate.parent)
        if shutil.disk_usage(parent).free < required:
            raise LatexRuntimeError(f"{parent} 可用空间不足")
        if create:
            candidate.parent.mkdir(parents=True, exist_ok=True)
        return candidate

    release = str(manifest["texlive_release"])
    project_drive = Path(project.resolve().anchor) if project.resolve().anchor else None
    drives = fixed_drives()
    ordered: list[Path] = []
    if project_drive and project_drive.drive.upper() != "C:":
        ordered.append(project_drive)
    ordered.extend(d for d in drives if d.drive.upper() != "C:" and d not in ordered)
    ordered.extend(d for d in drives if d.drive.upper() == "C:")
    for drive in ordered:
        candidate = drive / "math-paper-cn-runtime" / f"texlive-{release}"
        try:
            if is_inside(candidate, project) or not is_ascii_path(candidate):
                continue
            if shutil.disk_usage(drive).free < required:
                continue
            if create:
                candidate.parent.mkdir(parents=True, exist_ok=True)
            return candidate
        except OSError:
            continue
    raise LatexRuntimeError("没有找到可写、空间充足且位于项目外的 ASCII 运行时目录")


def executable(root: Path, name: str) -> Path | None:
    suffix = ".exe" if is_windows() else ""
    direct = root / "bin" / "windows" / f"{name}{suffix}"
    if direct.exists():
        return direct
    matches = list(root.glob(f"bin/*/{name}{suffix}"))
    return matches[0] if matches else None


def command_works(command: Path, version_arg: str = "--version") -> bool:
    try:
        proc = subprocess.run(
            [str(command), version_arg],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        return proc.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def command_version(command: Path) -> str:
    try:
        return subprocess.run(
            [str(command), "--version"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def discover(project: Path | None = None) -> Toolchain | None:
    portable_root = os.environ.get(PORTABLE_RUNTIME_ENV)
    if portable_root:
        alias_drive = os.environ.get(PORTABLE_ALIAS_ENV)
        root = (Path(f"{alias_drive}\\runtime") if alias_drive else Path(portable_root)) / "texlive"
        managed_latexmk = executable(root, "latexmk")
        managed_xelatex = executable(root, "xelatex")
        if managed_latexmk and managed_xelatex and command_works(managed_latexmk) and command_works(managed_xelatex):
            return Toolchain("bundled", process_path(managed_xelatex), process_path(managed_latexmk), process_path(executable(root, "tlmgr")) if executable(root, "tlmgr") else None, root)
        if os.environ.get(PORTABLE_STRICT_ENV) == "1":
            return None
    latexmk = shutil.which("latexmk")
    xelatex = shutil.which("xelatex")
    tlmgr = shutil.which("tlmgr")
    if latexmk and xelatex and command_works(Path(latexmk)) and command_works(Path(xelatex)):
        return Toolchain("host", Path(xelatex), Path(latexmk), Path(tlmgr) if tlmgr else None)
    if project:
        try:
            root = choose_runtime_root(project, minimum_free_bytes=1, create=False)
        except LatexRuntimeError:
            return None
        managed_latexmk = executable(root, "latexmk")
        managed_xelatex = executable(root, "xelatex")
        release = str(load_manifest()["texlive_release"])
        if (
            managed_latexmk
            and managed_xelatex
            and command_works(managed_latexmk)
            and command_works(managed_xelatex)
            and f"TeX Live {release}" in command_version(managed_xelatex)
        ):
            return Toolchain("managed", managed_xelatex, managed_latexmk, executable(root, "tlmgr"), root)
    return None


def sha512_file(path: Path) -> str:
    digest = hashlib.sha512()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download(url: str, output: Path, timeout: int = 120) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "math-paper-cn/1"})
    with urllib.request.urlopen(request, timeout=timeout) as response, output.open("wb") as handle:
        shutil.copyfileobj(response, handle)


def parse_sha512(text: str) -> str:
    match = re.search(r"\b([0-9a-fA-F]{128})\b", text)
    if not match:
        raise LatexRuntimeError("官方 SHA-512 文件格式无效")
    return match.group(1).lower()


def download_verified_installer(work: Path, mirrors: Iterable[str]) -> Path:
    manifest = load_manifest()
    archive_name = manifest["installer_archive"]
    checksum_name = manifest["installer_checksum"]
    failures: list[str] = []
    work.mkdir(parents=True, exist_ok=True)
    for mirror in mirrors:
        archive = work / archive_name
        checksum = work / checksum_name
        try:
            base = mirror.rstrip("/")
            if not checksum.exists():
                download(f"{base}/{checksum_name}", checksum)
            if not archive.exists():
                download(f"{base}/{archive_name}", archive)
            expected = parse_sha512(checksum.read_text(encoding="utf-8", errors="replace"))
            actual = sha512_file(archive)
            if actual != expected:
                archive.unlink(missing_ok=True)
                checksum.unlink(missing_ok=True)
                raise LatexRuntimeError(f"SHA-512 不匹配: {mirror}")
            return archive
        except (OSError, urllib.error.URLError, LatexRuntimeError) as exc:
            failures.append(f"{mirror}: {exc}")
            archive.unlink(missing_ok=True)
            checksum.unlink(missing_ok=True)
    raise LatexRuntimeError("所有官方安装镜像均失败；" + " | ".join(failures))


def offline_candidates() -> list[Path]:
    manifest = load_manifest()
    name = manifest["offline_archive"]
    candidates: list[Path] = []
    if os.environ.get(OFFLINE_ENV):
        candidates.append(Path(os.environ[OFFLINE_ENV]))
    candidates.extend([SKILL_ROOT / name, SKILL_ROOT.parent / name])
    return candidates


def safe_extract(bundle: zipfile.ZipFile, destination: Path) -> None:
    destination = destination.resolve()
    for member in bundle.infolist():
        target = (destination / member.filename).resolve()
        if not is_inside(target, destination):
            raise LatexRuntimeError(f"压缩包包含越界路径: {member.filename}")
    bundle.extractall(destination)


def install_offline(root: Path) -> bool:
    for archive in offline_candidates():
        if not archive.exists():
            continue
        checksum = archive.with_suffix(archive.suffix + ".sha256")
        if not checksum.exists():
            raise LatexRuntimeError(f"离线包缺少 SHA-256 文件: {checksum}")
        expected = re.search(r"\b([0-9a-fA-F]{64})\b", checksum.read_text(encoding="utf-8", errors="replace"))
        if not expected or sha256_file(archive) != expected.group(1).lower():
            raise LatexRuntimeError(f"离线包 SHA-256 校验失败: {archive}")
        root.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive) as bundle:
            safe_extract(bundle, root.parent)
        return executable(root, "xelatex") is not None
    return False


def render_profile(root: Path, output: Path) -> None:
    profile = PROFILE_PATH.read_text(encoding="utf-8")
    profile += f"\nTEXDIR {root.as_posix()}\n"
    profile += f"TEXMFCONFIG {root.as_posix()}/texmf-config\n"
    profile += f"TEXMFVAR {root.as_posix()}/texmf-var\n"
    profile += f"TEXMFHOME {root.as_posix()}/texmf-home\n"
    profile += f"TEXMFLOCAL {root.as_posix()}/texmf-local\n"
    profile += f"TEXMFSYSCONFIG {root.as_posix()}/texmf-config\n"
    profile += f"TEXMFSYSVAR {root.as_posix()}/texmf-var\n"
    output.write_text(profile, encoding="utf-8", newline="\n")


def run_installer(archive: Path, root: Path) -> None:
    root.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="installer-", dir=root.parent) as tmp:
        temp = Path(tmp)
        with zipfile.ZipFile(archive) as bundle:
            safe_extract(bundle, temp)
        batch_files = list(temp.rglob("install-tl-windows.bat"))
        if not batch_files:
            raise LatexRuntimeError("官方安装包中缺少 install-tl-windows.bat")
        profile = temp / "math-paper-cn.profile"
        render_profile(root, profile)
        proc = subprocess.run(
            ["cmd", "/d", "/c", str(batch_files[0]), "--profile", str(profile), "--no-interaction"],
            cwd=batch_files[0].parent,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=7200,
        )
        if proc.returncode != 0:
            raise LatexRuntimeError(f"TeX Live 安装失败（退出码 {proc.returncode}）: {proc.stdout[-2000:]}")


def bootstrap(project: Path) -> Toolchain:
    if not is_windows():
        raise LatexRuntimeError("LaTeX 自动自举仅正式支持简体中文 Windows 10/11")
    existing = discover(project)
    if existing:
        return existing
    root = choose_runtime_root(project)
    if install_offline(root):
        found = discover(project)
        if found:
            return found
    manifest = load_manifest()
    cache = root.parent / "downloads"
    archive = download_verified_installer(cache, manifest["mirrors"])
    run_installer(archive, root)
    found = discover(project)
    if not found:
        raise LatexRuntimeError("TeX Live 安装完成但未找到 latexmk 或 XeLaTeX")
    return found


def process_env(toolchain: Toolchain) -> dict[str, str]:
    env = os.environ.copy()
    bin_dir = str(toolchain.xelatex.parent)
    env["PATH"] = bin_dir + os.pathsep + env.get("PATH", "")
    env["PYTHONUTF8"] = "1"
    return env


def missing_packages(log_text: str) -> list[str]:
    names: list[str] = []
    for match in MISSING_FILE_RE.finditer(log_text):
        name = next((group for group in match.groups() if group), None)
        if name and name not in names:
            names.append(name)
    return names


def tlmgr_install_for_file(toolchain: Toolchain, filename: str) -> bool:
    if not toolchain.tlmgr:
        return False
    search = subprocess.run(
        [str(toolchain.tlmgr), "search", "--global", "--file", f"/{filename}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=process_env(toolchain),
        timeout=120,
    )
    packages = []
    for line in search.stdout.splitlines():
        if line and not line.startswith(" ") and line.endswith(":"):
            packages.append(line[:-1].strip())
    if not packages:
        return False
    install = subprocess.run(
        [str(toolchain.tlmgr), "install", packages[0]],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=process_env(toolchain),
        timeout=600,
    )
    return install.returncode == 0


def compile_tex(toolchain: Toolchain, tex_path: Path, output_dir: Path | None = None, retries: int = 3) -> dict:
    tex_path = tex_path.resolve()
    if not tex_path.exists():
        raise LatexRuntimeError(f"缺少 LaTeX 主文件: {tex_path}")
    output_dir = (output_dir or tex_path.parent).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    command = [
        str(toolchain.latexmk),
        "-xelatex",
        "-interaction=nonstopmode",
        "-halt-on-error",
        "-file-line-error",
        f"-outdir={output_dir}",
        tex_path.name,
    ]
    attempts: list[dict] = []
    for attempt in range(1, retries + 1):
        proc = subprocess.run(
            command,
            cwd=tex_path.parent,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=process_env(toolchain),
            timeout=1800,
        )
        attempts.append({"attempt": attempt, "returncode": proc.returncode, "tail": proc.stdout[-4000:]})
        if proc.returncode == 0 and (output_dir / f"{tex_path.stem}.pdf").exists():
            return {
                "ok": True,
                "backend": toolchain.source,
                "pdf": str(output_dir / f"{tex_path.stem}.pdf"),
                "log": str(output_dir / f"{tex_path.stem}.log"),
                "aux": str(output_dir / f"{tex_path.stem}.aux"),
                "attempts": attempts,
            }
        log_path = output_dir / f"{tex_path.stem}.log"
        text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else proc.stdout
        repaired = any(tlmgr_install_for_file(toolchain, name) for name in missing_packages(text))
        if not repaired:
            break
    return {"ok": False, "backend": toolchain.source, "attempts": attempts}


def smoke_test(toolchain: Toolchain) -> dict:
    template_path = SKILL_ROOT / "assets" / "templates" / "main.tex"
    template = template_path.read_text(encoding="utf-8")
    if "\\begin{document}" not in template:
        raise LatexRuntimeError(f"内置模板缺少 document 环境: {template_path}")
    preamble = template.split("\\begin{document}", 1)[0]
    source = preamble + r"""\begin{document}
宋体正文，{\sffamily 黑体测试}。Times New Roman. \(x^2+y^2=1\)
\end{document}
"""
    with tempfile.TemporaryDirectory(prefix="math-paper-cn-smoke-") as tmp:
        root = Path(tmp)
        for companion in template_path.parent.iterdir():
            if companion.is_file() and companion.name != template_path.name:
                shutil.copy2(companion, root / companion.name)
        tex = root / "smoke.tex"
        tex.write_text(source, encoding="utf-8")
        result = compile_tex(toolchain, tex, root)
        result["pdf_created"] = (root / "smoke.pdf").exists()
        result["log_created"] = (root / "smoke.log").exists()
        result["aux_created"] = (root / "smoke.aux").exists()
        result["template"] = "assets/templates/main.tex"
        result.pop("pdf", None)
        result.pop("log", None)
        result.pop("aux", None)
        result["fonts"] = load_manifest()["required_fonts"]
        return result


def sanitized(toolchain: Toolchain, smoke: dict | None = None) -> dict:
    version = subprocess.run(
        [str(toolchain.xelatex), "--version"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    ).stdout.splitlines()
    return {
        "ok": smoke is None or smoke.get("ok") is True,
        "source": toolchain.source,
        "version": version[0] if version else "unknown",
        "managed": toolchain.source == "managed",
        "fonts": load_manifest()["required_fonts"],
        "smoke_test": smoke,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="math-paper-cn Windows LaTeX 运行时管理器")
    parser.add_argument("action", choices=["probe", "bootstrap", "doctor", "compile"])
    parser.add_argument("--project", required=True, help="数学建模项目根目录")
    parser.add_argument("--tex", help="compile 动作的主 tex，默认 论文/main.tex")
    parser.add_argument("--output", help="结构化 JSON 报告")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    try:
        toolchain = discover(project)
        if args.action == "probe":
            if toolchain:
                report = sanitized(toolchain)
                report.update({"available": True, "deferred_install": False})
            else:
                report = {
                    "ok": True,
                    "available": False,
                    "deferred_install": True,
                    "install_stage": "step4_first_compile",
                }
        else:
            if not toolchain:
                toolchain = bootstrap(project)
            if not toolchain:
                raise LatexRuntimeError("未发现可用 LaTeX；运行 bootstrap 或 doctor 自动准备")
        if args.action == "compile":
            tex = Path(args.tex).resolve() if args.tex else project / "论文" / "main.tex"
            report = compile_tex(toolchain, tex)
        elif args.action == "doctor":
            report = sanitized(toolchain, smoke_test(toolchain))
        elif args.action == "bootstrap":
            report = sanitized(toolchain)
    except Exception as exc:
        report = {"ok": False, "error": str(exc), "type": type(exc).__name__}
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
    print(text)
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
