#!/usr/bin/env python3
"""校验并发现随 MetaMath Harness 分发的优秀论文。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any


CATALOG_SCHEMA = "dsh.excellent-papers.catalog/v1"
DEFAULT_LIMIT = 2


class CatalogError(ValueError):
    """目录清单结构错误。"""


def resolve_dsh_home(explicit: str | os.PathLike[str] | None = None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    configured = os.environ.get("DSH_HOME")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[3]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalize_problem(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().upper()
    normalized = re.sub(r"(?:题目?|PROBLEM)$", "", normalized, flags=re.IGNORECASE).strip()
    return normalized or None


def _result(
    status: str,
    root: Path,
    *,
    competition: str | None = None,
    problem: str | None = None,
    year: int | None = None,
    files: list[dict[str, Any]] | None = None,
    fallback_reason: str | None = None,
    problem_match: bool = False,
) -> dict[str, Any]:
    selected = files or []
    return {
        "status": status,
        "root": str(root),
        "competition": competition,
        "problem": problem,
        "year": year,
        "count": len(selected),
        "files": selected,
        "fallback_reason": fallback_reason,
        "problem_match": problem_match,
    }


def load_catalog(library_root: Path) -> dict[str, Any]:
    catalog_path = library_root / "catalog.json"
    try:
        raw = json.loads(catalog_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise CatalogError(f"catalog.json 无法解析：{error}") from error

    if not isinstance(raw, dict) or raw.get("schema") != CATALOG_SCHEMA:
        raise CatalogError(f"schema 必须为 {CATALOG_SCHEMA}")
    competitions = raw.get("competitions")
    papers = raw.get("papers")
    if not isinstance(competitions, dict) or not isinstance(papers, list):
        raise CatalogError("competitions 必须是对象，papers 必须是数组")

    canonical_names: set[str] = set()
    aliases: dict[str, str] = {}
    for canonical, values in competitions.items():
        if not isinstance(canonical, str) or not canonical.strip():
            raise CatalogError("赛事规范名必须是非空字符串")
        if not isinstance(values, list) or any(not isinstance(item, str) or not item.strip() for item in values):
            raise CatalogError(f"赛事 {canonical} 的别名必须是字符串数组")
        canonical_names.add(canonical)
        for alias in [canonical, *values]:
            key = alias.strip().casefold()
            if key in aliases and aliases[key] != canonical:
                raise CatalogError(f"赛事别名重复：{alias}")
            aliases[key] = canonical

    normalized_papers: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    resolved_root = library_root.resolve()
    for index, item in enumerate(papers):
        if not isinstance(item, dict):
            raise CatalogError(f"papers[{index}] 必须是对象")
        required = {"path", "competition", "year", "problem", "priority", "sha256"}
        if set(item) != required:
            raise CatalogError(f"papers[{index}] 字段必须恰好为 {sorted(required)}")
        relative = item["path"]
        if not isinstance(relative, str) or not relative.strip():
            raise CatalogError(f"papers[{index}].path 必须是非空字符串")
        pure = PurePosixPath(relative)
        if pure.is_absolute() or re.match(r"^[A-Za-z]:", relative) or "\\" in relative or ".." in pure.parts or "." in pure.parts:
            raise CatalogError(f"papers[{index}].path 禁止绝对路径或目录逃逸")
        if pure.suffix.casefold() != ".pdf":
            raise CatalogError(f"papers[{index}].path 必须是 PDF")
        key = pure.as_posix().casefold()
        if key in seen_paths:
            raise CatalogError(f"论文路径重复：{relative}")
        seen_paths.add(key)
        competition = item["competition"]
        if competition not in canonical_names:
            raise CatalogError(f"papers[{index}].competition 未在 competitions 登记")
        year = item["year"]
        if year is not None and (isinstance(year, bool) or not isinstance(year, int) or not 1900 <= year <= 2200):
            raise CatalogError(f"papers[{index}].year 必须是合理年份或 null")
        problem = item["problem"]
        if problem is not None and (not isinstance(problem, str) or normalize_problem(problem) != problem):
            raise CatalogError(f"papers[{index}].problem 必须是规范大写题号或 null")
        priority = item["priority"]
        if isinstance(priority, bool) or not isinstance(priority, int):
            raise CatalogError(f"papers[{index}].priority 必须是整数")
        digest = item["sha256"]
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise CatalogError(f"papers[{index}].sha256 必须是小写 SHA-256")
        absolute = (library_root / Path(*pure.parts)).resolve()
        try:
            absolute.relative_to(resolved_root)
        except ValueError as error:
            raise CatalogError(f"papers[{index}].path 逃逸论文库") from error
        normalized_papers.append({**item, "relativePath": pure.as_posix(), "absolutePath": absolute})

    return {"competitions": competitions, "aliases": aliases, "papers": normalized_papers}


def discover(
    *,
    dsh_home: str | os.PathLike[str] | None = None,
    competition: str | None = None,
    problem: str | None = None,
    year: int | None = None,
    limit: int = DEFAULT_LIMIT,
    disabled: bool = False,
    verify_all: bool = False,
) -> dict[str, Any]:
    home = resolve_dsh_home(dsh_home)
    library_root = home / "往年优秀论文"
    normalized_problem = normalize_problem(problem)
    if disabled:
        return _result("disabled", library_root, competition=competition, problem=normalized_problem, year=year, fallback_reason="优秀论文校准已关闭")
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        return _result("catalog_invalid", library_root, competition=competition, problem=normalized_problem, year=year, fallback_reason="limit 必须是正整数")
    try:
        catalog = load_catalog(library_root)
    except FileNotFoundError:
        return _result("catalog_missing", library_root, competition=competition, problem=normalized_problem, year=year, fallback_reason="未找到 catalog.json")
    except CatalogError as error:
        return _result("catalog_invalid", library_root, competition=competition, problem=normalized_problem, year=year, fallback_reason=str(error))

    if verify_all:
        candidates = list(catalog["papers"])
        canonical = None
        exact_problem = False
    else:
        if not isinstance(competition, str) or not competition.strip():
            return _result("no_matching_sample", library_root, problem=normalized_problem, year=year, fallback_reason="未提供赛事")
        canonical = catalog["aliases"].get(competition.strip().casefold())
        if canonical is None:
            return _result("no_matching_sample", library_root, competition=competition, problem=normalized_problem, year=year, fallback_reason="论文库没有该赛事")
        candidates = [item for item in catalog["papers"] if item["competition"] == canonical]
        exact_problem = normalized_problem is not None
        if normalized_problem is not None:
            candidates = [item for item in candidates if item["problem"] == normalized_problem]
        if year is not None:
            candidates = [item for item in candidates if item["year"] == year]
        if not candidates:
            return _result("no_matching_sample", library_root, competition=canonical, problem=normalized_problem, year=year, fallback_reason="暂无匹配样本", problem_match=False)

    candidates.sort(key=lambda item: (-item["priority"], item["relativePath"].casefold()))
    selected = candidates if verify_all else candidates[:limit]
    files: list[dict[str, Any]] = []
    for item in selected:
        path = item["absolutePath"]
        if not path.is_file():
            return _result("file_missing", library_root, competition=canonical, problem=normalized_problem, year=year, fallback_reason=f"清单文件不存在：{item['relativePath']}", problem_match=False)
        actual = sha256_file(path)
        if actual != item["sha256"]:
            return _result("hash_mismatch", library_root, competition=canonical, problem=normalized_problem, year=year, fallback_reason=f"文件哈希不一致：{item['relativePath']}", problem_match=False)
        files.append({
            "path": str(path),
            "relativePath": item["relativePath"],
            "competition": item["competition"],
            "year": item["year"],
            "problem": item["problem"],
            "priority": item["priority"],
            "sha256": item["sha256"],
        })

    return _result("matched", library_root, competition=canonical, problem=normalized_problem, year=year, files=files, problem_match=exact_problem)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="发现随程序分发的优秀论文")
    parser.add_argument("--dsh-home")
    parser.add_argument("--competition")
    parser.add_argument("--problem")
    parser.add_argument("--year", type=int)
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--disabled", action="store_true")
    parser.add_argument("--verify-all", action="store_true")
    return parser


def main() -> int:
    # Windows 控制台默认代码页可能不是 UTF-8；CLI 合同固定输出 UTF-8 JSON。
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args()
    result = discover(
        dsh_home=args.dsh_home,
        competition=args.competition,
        problem=args.problem,
        year=args.year,
        limit=args.limit,
        disabled=args.disabled,
        verify_all=args.verify_all,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.verify_all and result["status"] != "matched":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
