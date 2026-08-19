#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""运行 step0 至 step5 的累积硬门禁并维护项目阶段状态。"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from gate_registry import STAGES, gates_for, validate_registry


CHECK_DIR = Path(__file__).resolve().parent
LATEX_RUNNER = CHECK_DIR.parent / "latex" / "latex_runtime.py"
STATE_FILE = "项目状态.json"
CONTRACT_VERSION = 3
LAUNCHER_DIR = Path("scripts") / "checks"
ATTESTATION_FILE = Path("检查结果") / "delivery_attestation.json"
LAUNCHERS = {
    "run_stage_gate.py": [],
    "run_all_checks.py": ["--stage", "step5"],
    "verify_delivery.py": ["--verify-delivery"],
}
IGNORED_PARTS = {".git", ".venv", "__pycache__", "node_modules", "检查结果"}
STAGE_PATTERNS = {
    "step0": ("README.md", "AGENT.md", "data/source_map.md", "文献/source_map.md", "figures/manifest.json"),
    "step1": ("数据预处理/**/*", "data/**/*"),
    "step2": ("Q*/README.md", "Q*/model*.md", "Q*/模型*.md"),
    "step3": ("Q*/*.py", "Q*/result.md", "Q*/figures/**/*", "results/**/*", "figures/**/*", "手绘图/**/*"),
    "step4": ("论文/main.tex", "摘要/**/*", "灵敏度分析/**/*"),
    "step5": ("论文/**/*", "检查结果/三轮自查.md"),
}


class StageStateError(RuntimeError):
    """项目阶段状态不可安全读取。"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_state(project: Path) -> dict:
    path = project / STATE_FILE
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise StageStateError(f"项目状态.json 解析失败，已保留原文件: {exc}") from exc
    if not isinstance(data, dict):
        raise StageStateError("项目状态.json 顶层必须是对象，已保留原文件")
    return data


def save_state(project: Path, state: dict) -> None:
    state["workflow_version"] = CONTRACT_VERSION
    (project / STATE_FILE).write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_project_path(project: Path, value: object) -> Path | None:
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        return None
    candidate = (project / value).resolve()
    try:
        candidate.relative_to(project.resolve())
    except ValueError:
        return None
    return candidate


def launcher_source(default_args: list[str]) -> str:
    runner_hash = file_sha256(Path(__file__).resolve())
    return (
        "#!/usr/bin/env python\n"
        "# -*- coding: utf-8 -*-\n"
        '"""由 math-paper-cn 自动生成；不要改写或复制门禁逻辑。"""\n'
        "import hashlib\n"
        "from pathlib import Path\n"
        "import subprocess\n"
        "import sys\n\n"
        f"EXPECTED_SHA256 = {runner_hash!r}\n"
        f"DEFAULT_ARGS = {default_args!r}\n\n"
        "candidates = (\n"
        "    Path.home() / '.codex' / 'skills' / 'math-paper-cn' / 'scripts' / 'checks' / 'run_stage_gate.py',\n"
        "    Path.home() / '.trae-cn' / 'skills' / 'math-paper-cn' / 'scripts' / 'checks' / 'run_stage_gate.py',\n"
        ")\n"
        "RUNNER = next((path for path in candidates if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == EXPECTED_SHA256), None)\n"
        "if RUNNER is None:\n"
        "    raise SystemExit('门禁源缺失或版本已变化，请从当前 math-paper-cn Skill 重新运行 --init。')\n"
        "args = [sys.executable, str(RUNNER), *DEFAULT_ARGS, *sys.argv[1:]]\n"
        "raise SystemExit(subprocess.call(args))\n"
    )


def install_project_launchers(project: Path) -> dict[str, str]:
    """在项目内安装极小启动器，使文档命令与真实 Skill 入口一致。"""
    launcher_dir = project / LAUNCHER_DIR
    launcher_dir.mkdir(parents=True, exist_ok=True)
    hashes: dict[str, str] = {}
    for name, default_args in LAUNCHERS.items():
        path = launcher_dir / name
        content = launcher_source(default_args)
        path.write_text(content, encoding="utf-8")
        hashes[path.relative_to(project).as_posix()] = file_sha256(path)
    return hashes


def initialize_contract(project: Path, state: dict) -> None:
    previous = state.get("gate_contract")
    hashes = install_project_launchers(project)
    current = {
        "version": CONTRACT_VERSION,
        "runner_sha256": file_sha256(Path(__file__).resolve()),
        "registry_sha256": file_sha256(CHECK_DIR / "gate_registry.py"),
        "launchers": hashes,
        "initialized_at": previous.get("initialized_at") if isinstance(previous, dict) else utc_now(),
    }
    if not current["initialized_at"]:
        current["initialized_at"] = utc_now()
    comparable = ("version", "runner_sha256", "registry_sha256", "launchers")
    if isinstance(previous, dict) and any(previous.get(key) != current.get(key) for key in comparable):
        state["status"] = "in_progress"
        for record in state.get("stages", {}).values():
            if isinstance(record, dict) and record.get("status") == "passed":
                record["status"] = "stale"
                record["stale_at"] = utc_now()
    state["gate_contract"] = current


def migrate_state(project: Path, state: dict) -> None:
    """仅从已有产物补齐可确定的兼容字段，不猜测用户选择。"""
    if not isinstance(state.get("question_count"), int):
        numbers = []
        for path in project.glob("Q[0-9]*"):
            if path.is_dir() and path.name[1:].isdigit():
                numbers.append(int(path.name[1:]))
        if numbers and sorted(numbers) == list(range(1, max(numbers) + 1)):
            state["question_count"] = max(numbers)
    if state.get("data_mode") not in {"data", "none"}:
        data_dir = project / "data"
        real_data = [
            path
            for path in data_dir.rglob("*")
            if path.is_file() and path.name != "source_map.md"
        ] if data_dir.exists() else []
        preprocessing = project / "数据预处理" / "README.md"
        if real_data:
            state["data_mode"] = "data"
        elif preprocessing.exists() and "无数据依据" in preprocessing.read_text(encoding="utf-8", errors="replace"):
            state["data_mode"] = "none"


def artifact_paths(project: Path, stage: str) -> list[Path]:
    paths: set[Path] = set()
    for pattern in STAGE_PATTERNS[stage]:
        for path in project.glob(pattern):
            if not path.is_file() or any(part in IGNORED_PARTS for part in path.parts):
                continue
            paths.add(path)
    return sorted(paths, key=lambda item: item.as_posix())


def fingerprint(project: Path, stage: str) -> str:
    digest = hashlib.sha256()
    for path in artifact_paths(project, stage):
        digest.update(path.relative_to(project).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def invalidate_stale(project: Path, state: dict) -> int | None:
    stages = state.setdefault("stages", {})
    earliest: int | None = None
    for index, stage in enumerate(STAGES):
        record = stages.get(stage)
        if not isinstance(record, dict) or record.get("status") != "passed":
            continue
        if record.get("input_fingerprint") != fingerprint(project, stage):
            earliest = index if earliest is None else min(earliest, index)
    if earliest is not None:
        state["status"] = "in_progress"
        for stage in STAGES[earliest:]:
            record = stages.setdefault(stage, {})
            if record.get("status") == "passed":
                record["status"] = "stale"
                record["stale_at"] = utc_now()
    return earliest


def read_check_report(output: Path, script: str, proc: subprocess.CompletedProcess[str]) -> dict:
    try:
        return json.loads(output.read_text(encoding="utf-8"))
    except Exception:
        return {
            "check": Path(script).stem,
            "ok": proc.returncode == 0,
            "errors": [proc.stdout.strip() or f"{script} 未生成结构化报告"],
        }


def compile_paper(project: Path, output: Path) -> dict:
    tex = project / "论文" / "main.tex"
    if not tex.exists():
        return {"check": "compile_paper", "ok": False, "errors": ["缺少论文/main.tex，无法执行阶段编译"]}
    proc = subprocess.run(
        [
            sys.executable,
            str(LATEX_RUNNER),
            "compile",
            "--project",
            str(project),
            "--tex",
            str(tex),
            "--output",
            str(output),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    try:
        raw = json.loads(output.read_text(encoding="utf-8"))
    except Exception:
        raw = {"ok": False, "error": proc.stdout.strip()}
    return {
        "check": "compile_paper",
        "ok": raw.get("ok") is True,
        "errors": [] if raw.get("ok") is True else [raw.get("error") or "LaTeX 编译失败"],
        "details": raw,
    }


def write_markdown(path: Path, stage: str, results: list[dict], ok: bool) -> None:
    lines = [f"# {stage} 阶段门禁报告", "", f"总体状态：{'通过' if ok else '失败'}", ""]
    for item in results:
        lines.extend([f"## {item.get('check')}", f"- 状态：{'通过' if item.get('ok') else '失败'}"])
        lines.extend(f"- {error}" for error in item.get("errors", []))
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def run_one_stage(project: Path, stage: str, state: dict) -> bool:
    final = stage == "step5"
    report_dir = project / "检查结果" if final else project / "检查结果" / stage
    report_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []
    if STAGES.index(stage) >= 4:
        results.append(compile_paper(project, report_dir / "compile_paper.json"))
    for gate in gates_for(stage):
        output = report_dir / f"{Path(gate.script).stem}.json"
        command = [
            sys.executable,
            str(CHECK_DIR / gate.script),
            "--project",
            str(project),
            "--output",
            str(output),
        ]
        if gate.stage_argument:
            command.extend(["--stage", stage])
        proc = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        results.append(read_check_report(output, gate.script, proc))
    ok = all(item.get("ok") is True for item in results)
    summary = {"stage": stage, "ok": ok, "checks": results}
    summary_name = "check_report.json" if final else f"{stage}_gate.json"
    markdown_name = "check_report.md" if final else f"{stage}_gate.md"
    (report_dir / summary_name).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    summary_path = report_dir / summary_name
    write_markdown(report_dir / markdown_name, stage, results, ok)
    # 门禁失败时聚合全部失败项到单一清单，供单回合一次性读取并修复；通过时清理陈旧清单防止误读。
    failures_path = report_dir / "failures_summary.json"
    if ok:
        failures_path.unlink(missing_ok=True)
    else:
        failed_checks = []
        total_failures = 0
        for item in results:
            if item.get("ok") is True:
                continue
            issues = list(item.get("issues") or [])
            errors = list(item.get("errors") or [])
            total_failures += len(issues) if issues else len(errors)
            failed_checks.append({"check": item.get("check", "unknown"), "errors": errors, "issues": issues})
        failures_path.write_text(
            json.dumps(
                {
                    "stage": stage,
                    "generated_at": utc_now(),
                    "failed_check_count": len(failed_checks),
                    "total_failure_count": total_failures,
                    "failed_checks": failed_checks,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    record = state.setdefault("stages", {}).setdefault(stage, {})
    environment = next((item for item in results if item.get("check") == "check_latex_environment"), None)
    if environment and environment.get("ok") is True and environment.get("details", {}).get("source"):
        details = environment.get("details", {})
        state["latex_backend"] = {
            "source": details.get("source"),
            "version": details.get("version"),
            "managed": details.get("managed"),
            "fonts": details.get("fonts", []),
            "smoke_test": details.get("smoke_test", {}),
        }
    record.update(
        {
            "status": "passed" if ok else "failed",
            "input_fingerprint": fingerprint(project, stage),
            "report": str((report_dir / summary_name).relative_to(project)).replace("\\", "/"),
            "report_sha256": file_sha256(summary_path),
            "checked_at": utc_now(),
        }
    )
    if ok:
        record["completed_at"] = utc_now()
    save_state(project, state)
    return ok


def attestation_payload(project: Path, state: dict) -> dict:
    stages = {
        stage: {
            "status": state.get("stages", {}).get(stage, {}).get("status"),
            "input_fingerprint": fingerprint(project, stage),
            "report": state.get("stages", {}).get(stage, {}).get("report"),
            "report_sha256": state.get("stages", {}).get(stage, {}).get("report_sha256"),
        }
        for stage in STAGES
    }
    payload = {
        "contract_version": CONTRACT_VERSION,
        "project": str(project),
        "runner_sha256": file_sha256(Path(__file__).resolve()),
        "registry_sha256": file_sha256(CHECK_DIR / "gate_registry.py"),
        "gate_contract": state.get("gate_contract"),
        "stages": stages,
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    payload["attestation_sha256"] = hashlib.sha256(canonical).hexdigest()
    return payload


def write_attestation(project: Path, state: dict) -> None:
    path = project / ATTESTATION_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(attestation_payload(project, state), ensure_ascii=False, indent=2), encoding="utf-8")


def verify_delivery(project: Path) -> tuple[bool, list[str]]:
    errors: list[str] = []
    try:
        state = load_state(project)
    except StageStateError as exc:
        return False, [str(exc)]
    if state.get("status") != "completed":
        errors.append("项目状态不是 completed，禁止交付。")
    contract = state.get("gate_contract", {})
    if contract.get("version") != CONTRACT_VERSION:
        errors.append("门禁契约版本缺失或已过期。")
    if contract.get("runner_sha256") != file_sha256(Path(__file__).resolve()):
        errors.append("门禁运行器版本与项目契约不一致。")
    if contract.get("registry_sha256") != file_sha256(CHECK_DIR / "gate_registry.py"):
        errors.append("门禁注册表版本与项目契约不一致。")
    expected_launchers = contract.get("launchers", {})
    for relative, expected_hash in expected_launchers.items():
        path = safe_project_path(project, relative)
        if path is None or not path.is_file() or file_sha256(path) != expected_hash:
            errors.append(f"项目门禁启动器缺失或被修改: {relative}")
    for stage in STAGES:
        record = state.get("stages", {}).get(stage, {})
        if record.get("status") != "passed":
            errors.append(f"{stage} 未通过。")
            continue
        if record.get("input_fingerprint") != fingerprint(project, stage):
            errors.append(f"{stage} 产物在门禁通过后发生变化。")
        report = safe_project_path(project, record.get("report"))
        if report is None:
            errors.append(f"{stage} 门禁报告路径非法。")
            continue
        if not report.is_file():
            errors.append(f"{stage} 缺少门禁报告。")
            continue
        if record.get("report_sha256") != file_sha256(report):
            errors.append(f"{stage} 门禁报告在通过后被修改。")
        try:
            report_data = json.loads(report.read_text(encoding="utf-8"))
        except Exception:
            errors.append(f"{stage} 门禁报告无法解析。")
            continue
        if report_data.get("ok") is not True or report_data.get("stage") != stage:
            errors.append(f"{stage} 门禁报告未通过或阶段不匹配。")
            continue
        expected_checks = [Path(gate.script).stem for gate in gates_for(stage)]
        if STAGES.index(stage) >= 4:
            expected_checks.insert(0, "compile_paper")
        actual_checks = [item.get("check") for item in report_data.get("checks", []) if isinstance(item, dict)]
        if actual_checks != expected_checks:
            errors.append(f"{stage} 门禁报告检查项不完整、重复或顺序异常。")
        elif not all(item.get("ok") is True for item in report_data["checks"]):
            errors.append(f"{stage} 门禁报告包含失败检查项。")
    attestation = project / ATTESTATION_FILE
    if not attestation.is_file():
        errors.append("缺少最终交付凭证。")
    else:
        try:
            actual = json.loads(attestation.read_text(encoding="utf-8"))
        except Exception:
            actual = None
        if actual != attestation_payload(project, state):
            errors.append("最终交付凭证与当前项目内容不一致。")
    return not errors, errors


def initialize_project(project: Path) -> int:
    if not project.is_dir():
        print(json.dumps({"ok": False, "errors": [f"项目根目录不存在: {project}"]}, ensure_ascii=False, indent=2))
        return 2
    try:
        state = load_state(project)
    except StageStateError as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, ensure_ascii=False, indent=2))
        return 2
    initialize_contract(project, state)
    state.setdefault("status", "in_progress")
    save_state(project, state)
    print(json.dumps({"ok": True, "initialized": True, "launchers": sorted(state["gate_contract"]["launchers"])}, ensure_ascii=False, indent=2))
    return 0


def run_through(project: Path, target: str) -> int:
    if not project.is_dir():
        print(json.dumps({"ok": False, "errors": [f"项目根目录不存在: {project}"]}, ensure_ascii=False, indent=2))
        return 2
    registry_errors = validate_registry()
    if registry_errors:
        print(json.dumps({"ok": False, "errors": registry_errors}, ensure_ascii=False, indent=2))
        return 2
    try:
        state = load_state(project)
    except StageStateError as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, ensure_ascii=False, indent=2))
        return 2
    migrate_state(project, state)
    initialize_contract(project, state)
    invalidate_stale(project, state)
    if target == "step5":
        state["status"] = "validating"
    save_state(project, state)
    target_index = STAGES.index(target)
    for stage in STAGES[: target_index + 1]:
        record = state.setdefault("stages", {}).get(stage, {})
        force_target = stage == target
        if (
            not force_target
            and record.get("status") == "passed"
            and record.get("input_fingerprint") == fingerprint(project, stage)
        ):
            continue
        if not run_one_stage(project, stage, state):
            state["status"] = "failed" if target == "step5" else "in_progress"
            save_state(project, state)
            failures_rel = (
                Path("检查结果") / "failures_summary.json"
                if stage == "step5"
                else Path("检查结果") / stage / "failures_summary.json"
            ).as_posix()
            print(json.dumps({"ok": False, "failed_stage": stage, "failures_summary": failures_rel}, ensure_ascii=False, indent=2))
            return 1
    if target == "step5":
        state["status"] = "completed"
        state["completed_at"] = utc_now()
        save_state(project, state)
        write_attestation(project, state)
    print(json.dumps({"ok": True, "stage": target}, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="运行 math-paper-cn 逐阶段硬门禁")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--stage", choices=STAGES, help="运行至指定阶段")
    group.add_argument("--through", choices=STAGES, help="运行至指定阶段")
    group.add_argument("--init", action="store_true", help="在项目内安装固定门禁入口并初始化状态")
    group.add_argument("--verify-delivery", action="store_true", help="只读验证最终交付凭证与全部阶段状态")
    parser.add_argument("--project", required=True, help="数学建模项目根目录")
    parser.add_argument("--resume", action="store_true", help="从最早未通过或失效阶段继续")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    if args.init:
        return initialize_project(project)
    if args.verify_delivery:
        ok, errors = verify_delivery(project)
        print(json.dumps({"ok": ok, "errors": errors}, ensure_ascii=False, indent=2))
        return 0 if ok else 1
    return run_through(project, args.stage or args.through)


if __name__ == "__main__":
    raise SystemExit(main())
