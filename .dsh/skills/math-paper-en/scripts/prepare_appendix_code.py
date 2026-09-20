#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""生成并验证论文附录中的 Python 等价净化副本。"""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import keyword
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


CONFIG_REL = Path("检查结果") / "附录代码复核.json"
APPENDIX_ROOT = Path("论文") / "附录代码"
REFLECTION_CALLS = {"eval", "exec", "locals", "globals", "vars"}
IGNORE_COPY = shutil.ignore_patterns(".git", ".venv", "venv", "__pycache__", "node_modules")
CODING_RE = re.compile(r"^#.*coding[:=]\s*[-\w.]+")


class ConfigError(ValueError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def project_path(project: Path, rel: str, *, under: Path | None = None) -> Path:
    candidate = Path(rel)
    if candidate.is_absolute():
        raise ConfigError(f"路径必须相对项目根目录: {rel}")
    resolved = (project / candidate).resolve()
    try:
        resolved.relative_to(project.resolve())
    except ValueError as exc:
        raise ConfigError(f"路径越出项目根目录: {rel}") from exc
    if under is not None:
        base = (project / under).resolve()
        try:
            resolved.relative_to(base)
        except ValueError as exc:
            raise ConfigError(f"附录净化文件必须位于 `{under.as_posix()}/`: {rel}") from exc
    return resolved


def load_config(project: Path) -> tuple[Path, dict[str, Any]]:
    path = project / CONFIG_REL
    if not path.exists():
        raise ConfigError(f"缺少附录代码复核配置: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ConfigError(f"附录代码复核配置解析失败: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError("附录代码复核配置必须是 JSON 对象。")
    if not isinstance(data.get("files"), list) or not data["files"]:
        raise ConfigError("附录代码复核配置必须包含非空 `files` 列表。")
    if not isinstance(data.get("runs"), list) or not data["runs"]:
        raise ConfigError("附录代码复核配置必须包含非空 `runs` 列表。")
    return path, data


def strip_docstrings(tree: ast.AST) -> ast.AST:
    class Cleaner(ast.NodeTransformer):
        def clean_body(self, body: list[ast.stmt]) -> list[ast.stmt]:
            cleaned = [self.visit(item) for item in body]
            result = [item for item in cleaned if item is not None]
            if result and isinstance(result[0], ast.Expr):
                value = result[0].value
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    result.pop(0)
            return result or [ast.Pass()]

        def visit_Module(self, node: ast.Module) -> ast.AST:
            node.body = self.clean_body(node.body)
            return node

        def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
            node.body = self.clean_body(node.body)
            return node

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
            node.body = self.clean_body(node.body)
            return node

        def visit_ClassDef(self, node: ast.ClassDef) -> ast.AST:
            node.body = self.clean_body(node.body)
            return node

    return Cleaner().visit(tree)


def function_nodes(tree: ast.AST) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    result: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}

    class Finder(ast.NodeVisitor):
        def __init__(self) -> None:
            self.stack: list[str] = []

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            self.stack.append(node.name)
            for item in node.body:
                self.visit(item)
            self.stack.pop()

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self.add(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self.add(node)

        def add(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
            self.stack.append(node.name)
            name = ".".join(self.stack)
            if name in result:
                raise ConfigError(f"函数限定名重复，无法安全改名: {name}")
            result[name] = node
            for item in node.body:
                self.visit(item)
            self.stack.pop()

    Finder().visit(tree)
    return result


def local_info(node: ast.FunctionDef | ast.AsyncFunctionDef) -> dict[str, set[str] | bool]:
    assigned: set[str] = set()
    args = {
        item.arg
        for item in (
            list(node.args.posonlyargs)
            + list(node.args.args)
            + list(node.args.kwonlyargs)
            + ([node.args.vararg] if node.args.vararg else [])
            + ([node.args.kwarg] if node.args.kwarg else [])
        )
    }
    imported: set[str] = set()
    declared: set[str] = set()
    nested_loads: set[str] = set()
    reflection = False

    class ScopeVisitor(ast.NodeVisitor):
        def visit_FunctionDef(self, child: ast.FunctionDef) -> None:
            if child is node:
                for item in child.body:
                    self.visit(item)
            else:
                nested_loads.update(
                    item.id
                    for item in ast.walk(child)
                    if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Load)
                )

        def visit_AsyncFunctionDef(self, child: ast.AsyncFunctionDef) -> None:
            self.visit_FunctionDef(child)

        def visit_Lambda(self, child: ast.Lambda) -> None:
            nested_loads.update(
                item.id
                for item in ast.walk(child)
                if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Load)
            )

        def visit_ClassDef(self, child: ast.ClassDef) -> None:
            return

        def visit_Name(self, child: ast.Name) -> None:
            if isinstance(child.ctx, ast.Store):
                assigned.add(child.id)

        def visit_Import(self, child: ast.Import) -> None:
            for alias in child.names:
                imported.add(alias.asname or alias.name.split(".", 1)[0])

        def visit_ImportFrom(self, child: ast.ImportFrom) -> None:
            for alias in child.names:
                imported.add(alias.asname or alias.name)

        def visit_Global(self, child: ast.Global) -> None:
            declared.update(child.names)

        def visit_Nonlocal(self, child: ast.Nonlocal) -> None:
            declared.update(child.names)

        def visit_Call(self, child: ast.Call) -> None:
            nonlocal reflection
            if isinstance(child.func, ast.Name) and child.func.id in REFLECTION_CALLS:
                reflection = True
            self.generic_visit(child)

    ScopeVisitor().visit(node)
    return {
        "locals": assigned - args - imported - declared,
        "args": args,
        "imported": imported,
        "declared": declared,
        "nested_loads": nested_loads,
        "reflection": reflection,
    }


def normalized_maps(
    tree: ast.AST,
    rename_map: Any,
    keep_long_names: Any,
) -> dict[str, dict[str, str]]:
    if rename_map is None:
        rename_map = {}
    if keep_long_names is None:
        keep_long_names = {}
    if not isinstance(rename_map, dict) or not isinstance(keep_long_names, dict):
        raise ConfigError("`rename_map` 和 `keep_long_names` 必须是按函数限定名分组的对象。")
    funcs = function_nodes(tree)
    result: dict[str, dict[str, str]] = {}
    for qual, raw_map in rename_map.items():
        if qual not in funcs:
            raise ConfigError(f"`rename_map` 引用了不存在的函数: {qual}")
        if not isinstance(raw_map, dict):
            raise ConfigError(f"`rename_map.{qual}` 必须是对象。")
        info = local_info(funcs[qual])
        locals_set = set(info["locals"])
        keep = keep_long_names.get(qual, {})
        if not isinstance(keep, dict) or any(not str(reason).strip() for reason in keep.values()):
            raise ConfigError(f"`keep_long_names.{qual}` 必须为名称到非空理由的对象。")
        if info["reflection"] and raw_map:
            raise ConfigError(f"函数 `{qual}` 使用名称反射，禁止自动改名。")
        new_names: set[str] = set()
        for old, new in raw_map.items():
            if old not in locals_set:
                raise ConfigError(f"`{qual}.{old}` 不是可安全修改的函数局部赋值变量。")
            if old in info["nested_loads"]:
                raise ConfigError(f"`{qual}.{old}` 被嵌套作用域引用，禁止自动改名。")
            if not isinstance(new, str) or not new.isidentifier() or keyword.iskeyword(new):
                raise ConfigError(f"`{qual}.{old}` 的新名称不是合法标识符: {new!r}")
            if len(new) > 16:
                raise ConfigError(f"`{qual}.{old}` 的新名称超过 16 个字符: {new}")
            if new != old and new in locals_set - {old}:
                raise ConfigError(f"`{qual}.{old}` 的新名称与现有局部变量冲突: {new}")
            if new in new_names:
                raise ConfigError(f"`{qual}` 中多个变量被改为同一名称: {new}")
            new_names.add(new)
        for name in locals_set:
            if len(name) > 16 and name not in raw_map and name not in keep:
                raise ConfigError(
                    f"局部变量 `{qual}.{name}` 超过 16 个字符；请在 rename_map 中缩短，"
                    "或在 keep_long_names 中写明保留理由。"
                )
        result[str(qual)] = {str(old): str(new) for old, new in raw_map.items()}
    return result


def rename_locals(tree: ast.AST, maps: dict[str, dict[str, str]]) -> ast.AST:
    class Renamer(ast.NodeTransformer):
        def __init__(self) -> None:
            self.stack: list[str] = []

        def visit_ClassDef(self, node: ast.ClassDef) -> ast.AST:
            self.stack.append(node.name)
            node = self.generic_visit(node)
            self.stack.pop()
            return node

        def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
            return self.visit_function(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
            return self.visit_function(node)

        def visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> ast.AST:
            self.stack.append(node.name)
            node = self.generic_visit(node)
            self.stack.pop()
            return node

        def visit_Name(self, node: ast.Name) -> ast.AST:
            mapping = maps.get(".".join(self.stack), {})
            if node.id in mapping:
                node.id = mapping[node.id]
            return node

    return Renamer().visit(tree)


def source_header(text: str) -> str:
    lines = text.splitlines()
    header: list[str] = []
    if lines and lines[0].startswith("#!"):
        header.append(lines[0])
    for line in lines[:2]:
        if CODING_RE.match(line) and line not in header:
            header.append(line)
    return "\n".join(header)


def sanitize_python(source: Path, item: dict[str, Any]) -> str:
    text = source.read_text(encoding="utf-8")
    try:
        tree = ast.parse(text, filename=str(source))
    except SyntaxError as exc:
        raise ConfigError(f"Python 源文件语法错误 {source}: {exc}") from exc
    maps = normalized_maps(tree, item.get("rename_map"), item.get("keep_long_names"))
    tree = strip_docstrings(tree)
    tree = rename_locals(tree, maps)
    ast.fix_missing_locations(tree)
    body = ast.unparse(tree).strip() + "\n"
    header = source_header(text)
    result = f"{header}\n{body}" if header else body
    compile(result, str(source), "exec")
    return result


def file_entries(project: Path, config: dict[str, Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    seen_sources: set[Path] = set()
    seen_appendix: set[Path] = set()
    for raw in config["files"]:
        if not isinstance(raw, dict):
            raise ConfigError("`files` 条目必须是对象。")
        source = project_path(project, str(raw.get("source", "")))
        appendix = project_path(project, str(raw.get("appendix", "")), under=APPENDIX_ROOT)
        if source.suffix.lower() != ".py" or appendix.suffix.lower() != ".py":
            raise ConfigError("附录自动净化仅支持 `.py` 文件。")
        if not source.exists():
            raise ConfigError(f"真实源文件不存在: {source}")
        if source in seen_sources or appendix in seen_appendix:
            raise ConfigError("`files` 中 source 或 appendix 存在重复。")
        seen_sources.add(source)
        seen_appendix.add(appendix)
        entries.append({"raw": raw, "source": source, "appendix": appendix})
    return entries


def numeric(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        return None


def compare_json(left: Any, right: Any, abs_tol: float, rel_tol: float, path: str = "$") -> list[str]:
    errors: list[str] = []
    if isinstance(left, bool) or isinstance(right, bool):
        if left != right:
            errors.append(f"{path}: {left!r} != {right!r}")
    elif isinstance(left, (int, float)) and isinstance(right, (int, float)):
        if not math.isclose(float(left), float(right), abs_tol=abs_tol, rel_tol=rel_tol):
            errors.append(f"{path}: {left!r} != {right!r}")
    elif type(left) is not type(right):
        errors.append(f"{path}: 类型不同 {type(left).__name__} != {type(right).__name__}")
    elif isinstance(left, dict):
        if set(left) != set(right):
            errors.append(f"{path}: JSON 键集合不同")
        else:
            for key in sorted(left):
                errors.extend(compare_json(left[key], right[key], abs_tol, rel_tol, f"{path}.{key}"))
    elif isinstance(left, list):
        if len(left) != len(right):
            errors.append(f"{path}: JSON 列表长度不同")
        else:
            for index, (a, b) in enumerate(zip(left, right)):
                errors.extend(compare_json(a, b, abs_tol, rel_tol, f"{path}[{index}]"))
    elif left != right:
        errors.append(f"{path}: {left!r} != {right!r}")
    return errors


def compare_csv(left: Path, right: Path, abs_tol: float, rel_tol: float) -> list[str]:
    with left.open("r", encoding="utf-8-sig", newline="") as handle:
        rows_left = list(csv.reader(handle))
    with right.open("r", encoding="utf-8-sig", newline="") as handle:
        rows_right = list(csv.reader(handle))
    if len(rows_left) != len(rows_right):
        return ["CSV 行数不同。"]
    errors: list[str] = []
    for row_index, (row_left, row_right) in enumerate(zip(rows_left, rows_right), 1):
        if len(row_left) != len(row_right):
            errors.append(f"CSV 第 {row_index} 行列数不同。")
            continue
        for column, (left_value, right_value) in enumerate(zip(row_left, row_right), 1):
            a, b = numeric(left_value), numeric(right_value)
            if a is not None and b is not None:
                if not math.isclose(a, b, abs_tol=abs_tol, rel_tol=rel_tol):
                    errors.append(f"CSV 第 {row_index} 行第 {column} 列数值不同。")
            elif left_value != right_value:
                errors.append(f"CSV 第 {row_index} 行第 {column} 列文本不同。")
    return errors


def compare_output(left: Path, right: Path, kind: str, abs_tol: float, rel_tol: float) -> list[str]:
    if not left.exists() or not right.exists():
        return [f"输出文件缺失: {left.name}"]
    if kind == "json":
        try:
            a = json.loads(left.read_text(encoding="utf-8"))
            b = json.loads(right.read_text(encoding="utf-8"))
        except Exception as exc:
            return [f"JSON 输出解析失败: {exc}"]
        return compare_json(a, b, abs_tol, rel_tol)
    if kind == "csv":
        return compare_csv(left, right, abs_tol, rel_tol)
    if kind == "text":
        a = left.read_text(encoding="utf-8").replace("\r\n", "\n")
        b = right.read_text(encoding="utf-8").replace("\r\n", "\n")
        return [] if a == b else ["文本输出不同。"]
    if kind == "binary":
        return [] if sha256(left) == sha256(right) else ["二进制输出哈希不同。"]
    return [f"不支持的输出类型: {kind}"]


def command_args(command: Any) -> list[str]:
    if not isinstance(command, list) or not command or not all(isinstance(item, str) and item for item in command):
        raise ConfigError("回归命令必须是非空字符串数组，禁止使用 shell 字符串。")
    result = list(command)
    if result[0] in {"python", "python3", "{python}"}:
        result[0] = sys.executable
    return result


def run_case(root: Path, run: dict[str, Any]) -> subprocess.CompletedProcess[str]:
    command = command_args(run.get("command"))
    cwd_rel = str(run.get("cwd", "."))
    cwd = project_path(root, cwd_rel)
    if not cwd.is_dir():
        raise ConfigError(f"回归运行目录不存在: {cwd_rel}")
    timeout = int(run.get("timeout", 120))
    if timeout <= 0:
        raise ConfigError("回归超时时间必须为正整数。")
    env = os.environ.copy()
    raw_env = run.get("env", {})
    if not isinstance(raw_env, dict):
        raise ConfigError("回归 `env` 必须是对象。")
    env.update({str(key): str(value) for key, value in raw_env.items()})
    return subprocess.run(
        command,
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=timeout,
        env=env,
        shell=False,
    )


def verify_runs(
    project: Path,
    config: dict[str, Any],
    entries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    abs_tol = float(config.get("tolerance", {}).get("abs", 1e-9))
    rel_tol = float(config.get("tolerance", {}).get("rel", 1e-9))
    appendix_map = {
        str(entry["raw"]["appendix"]): str(entry["raw"]["source"])
        for entry in entries
    }
    covered: set[str] = set()
    reports: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="math-paper-appendix-") as temp:
        base = Path(temp)
        original = base / "original"
        sanitized = base / "sanitized"
        shutil.copytree(project, original, ignore=IGNORE_COPY)
        shutil.copytree(project, sanitized, ignore=IGNORE_COPY)
        for appendix_rel, source_rel in appendix_map.items():
            clean_file = project_path(project, appendix_rel, under=APPENDIX_ROOT)
            target = project_path(sanitized, source_rel)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(clean_file, target)
        for index, raw_run in enumerate(config["runs"], 1):
            if not isinstance(raw_run, dict):
                raise ConfigError("`runs` 条目必须是对象。")
            name = str(raw_run.get("name") or f"run-{index}")
            files = raw_run.get("files")
            outputs = raw_run.get("outputs")
            if not isinstance(files, list) or not files:
                raise ConfigError(f"回归 `{name}` 必须列出覆盖的附录文件。")
            if not isinstance(outputs, list) or not outputs:
                raise ConfigError(f"回归 `{name}` 必须列出结构化输出文件。")
            for rel in files:
                if rel not in appendix_map:
                    raise ConfigError(f"回归 `{name}` 引用了未配置的附录文件: {rel}")
                covered.add(rel)
            for output in outputs:
                if not isinstance(output, dict) or not output.get("path") or not output.get("type"):
                    raise ConfigError(f"回归 `{name}` 的 outputs 条目必须包含 path 和 type。")
                for root in (original, sanitized):
                    out = project_path(root, str(output["path"]))
                    if out.exists():
                        if out.is_dir():
                            shutil.rmtree(out)
                        else:
                            out.unlink()
            try:
                original_run = run_case(original, raw_run)
                sanitized_run = run_case(sanitized, raw_run)
            except subprocess.TimeoutExpired as exc:
                raise ConfigError(f"回归 `{name}` 超时: {exc}") from exc
            if original_run.returncode != 0:
                raise ConfigError(f"原版回归 `{name}` 运行失败: {original_run.stderr or original_run.stdout}")
            if sanitized_run.returncode != 0:
                raise ConfigError(f"净化版回归 `{name}` 运行失败: {sanitized_run.stderr or sanitized_run.stdout}")
            output_reports: list[dict[str, str]] = []
            for output in outputs:
                rel = str(output["path"])
                kind = str(output["type"]).lower()
                left = project_path(original, rel)
                right = project_path(sanitized, rel)
                differences = compare_output(left, right, kind, abs_tol, rel_tol)
                if differences:
                    raise ConfigError(f"回归 `{name}` 输出 `{rel}` 不一致: " + "；".join(differences[:10]))
                output_reports.append(
                    {
                        "path": rel,
                        "type": kind,
                        "original_sha256": sha256(left),
                        "sanitized_sha256": sha256(right),
                    }
                )
            reports.append({"name": name, "ok": True, "outputs": output_reports})
    missing = sorted(set(appendix_map) - covered)
    if missing:
        raise ConfigError("以下附录文件未被任何回归用例覆盖: " + "、".join(missing))
    return reports


def prepare(project: Path, *, verify_only: bool) -> dict[str, Any]:
    config_path, config = load_config(project)
    entries = file_entries(project, config)
    file_reports: list[dict[str, str]] = []
    for entry in entries:
        expected = sanitize_python(entry["source"], entry["raw"])
        appendix = entry["appendix"]
        if verify_only:
            if not appendix.exists():
                raise ConfigError(f"附录净化文件不存在: {appendix}")
            if appendix.read_text(encoding="utf-8") != expected:
                raise ConfigError(f"附录净化文件不是当前源文件和 rename_map 的确定性结果: {appendix}")
        else:
            appendix.parent.mkdir(parents=True, exist_ok=True)
            appendix.write_text(expected, encoding="utf-8", newline="\n")
        file_reports.append(
            {
                "source": str(entry["raw"]["source"]),
                "appendix": str(entry["raw"]["appendix"]),
                "source_sha256": sha256(entry["source"]),
                "appendix_sha256": sha256(appendix),
            }
        )
    run_reports = verify_runs(project, config, entries)
    report = {
        "ok": True,
        "tolerance": {
            "abs": float(config.get("tolerance", {}).get("abs", 1e-9)),
            "rel": float(config.get("tolerance", {}).get("rel", 1e-9)),
        },
        "files": file_reports,
        "runs": run_reports,
    }
    if verify_only:
        recorded = config.get("verification")
        if not isinstance(recorded, dict) or recorded.get("ok") is not True:
            raise ConfigError("附录代码复核配置缺少成功的 `verification` 记录。")
        if recorded.get("files") != file_reports:
            raise ConfigError("附录代码复核配置中的文件哈希记录已过期。")
    else:
        config["verification"] = report
        config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="生成并验证论文附录中的 Python 等价净化副本。")
    parser.add_argument("--project", required=True, help="数学建模项目根目录")
    parser.add_argument("--verify", action="store_true", help="只读验证，不生成或修改文件")
    args = parser.parse_args()
    try:
        report = prepare(Path(args.project).resolve(), verify_only=args.verify)
    except Exception as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
