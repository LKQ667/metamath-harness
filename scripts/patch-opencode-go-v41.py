#!/usr/bin/env python3
"""为 DSH 内置 OpenCode Go 目录补充 DeepSeek V4.1 Flash（幂等热补丁）。

证据（2026-09-10）：
- https://opencode.ai/zh/go：data-model="deepseek-flash" 对应 DeepSeek V4.1 Flash；
- https://opencode.ai/zen/go/v1/models：实时目录唯一返回 deepseek-flash；
- https://models.dev/api.json：opencode-go/deepseek-flash 的完整元数据。

用法：
    python scripts/patch-opencode-go-v41.py
    python scripts/patch-opencode-go-v41.py --check

升级失败关闭：若上游已收录则直接通过；若 pi-ai 不再是已验证的 0.84.4，
或旧目录语义发生变化，则拒绝修改，必须重新三方核对。
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


VERIFIED_PI_AI_VERSION = "0.84.4"
MODEL_ID = "deepseek-flash"
BACKUP_SUFFIX = ".bak-before-deepseek-v41"


def fail(message: str) -> None:
    print(f"[FAIL] {message}", file=sys.stderr)
    raise SystemExit(1)


def default_catalog() -> Path:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        fail("环境变量 APPDATA 未设置；请显式传入 opencode-go.json 路径")
    return (
        Path(appdata)
        / "npm"
        / "node_modules"
        / "@deepseek-ai"
        / "dsh"
        / "node_modules"
        / "@earendil-works"
        / "pi-ai"
        / "dist"
        / "providers"
        / "data"
        / "opencode-go.json"
    )


def load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        fail(f"无法读取 JSON：{path}：{error}")
    if not isinstance(value, dict):
        fail("目录根节点不是对象")
    return value


def package_version(catalog: Path) -> str:
    package_json = catalog.parents[3] / "package.json"
    package = load_json(package_json)
    version = package.get("version")
    if not isinstance(version, str):
        fail(f"无法读取 pi-ai 版本：{package_json}")
    return version


def expected_model() -> dict:
    return {
        "id": MODEL_ID,
        "name": "DeepSeek V4.1 Flash",
        "api": "openai-completions",
        "provider": "opencode-go",
        "baseUrl": "https://opencode.ai/zen/go/v1",
        "reasoning": True,
        "input": ["text", "image"],
        "cost": {"input": 0.15, "output": 0.6, "cacheRead": 0.003, "cacheWrite": 0},
        "compat": {
            "supportsStore": False,
            "supportsDeveloperRole": False,
            "maxTokensField": "max_tokens",
            "requiresReasoningContentOnAssistantMessages": True,
            "thinkingFormat": "deepseek",
        },
        "contextWindow": 1_000_000,
        "maxTokens": 384_000,
        "thinkingLevelMap": {
            "minimal": None,
            "low": "low",
            "medium": None,
            "high": "high",
            "max": "max",
        },
    }


def verify(catalog: dict) -> None:
    protocols = catalog.get("openai-completions")
    if not isinstance(protocols, dict):
        fail("缺少 openai-completions 目录")
    actual = protocols.get(MODEL_ID)
    if actual != expected_model():
        fail(f"{MODEL_ID} 元数据不符合已核验证据")
    occurrences = sum(
        1
        for group in catalog.values()
        if isinstance(group, dict)
        for model_id in group
        if model_id == MODEL_ID
    )
    if occurrences != 1:
        fail(f"{MODEL_ID} 出现次数异常：{occurrences}")


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenCode Go DeepSeek V4.1 Flash 目录补丁")
    parser.add_argument("--check", action="store_true", help="只检查，不修改")
    parser.add_argument("target", nargs="?", default=str(default_catalog()))
    args = parser.parse_args()

    target = Path(args.target)
    if not target.is_file():
        fail(f"目标文件不存在：{target}")
    catalog = load_json(target)
    models = catalog.get("openai-completions")
    if not isinstance(models, dict):
        fail("缺少 openai-completions 目录")

    if MODEL_ID in models:
        verify(catalog)
        print(f"[OK] {MODEL_ID} 已由目录收录且元数据正确，无需重打")
        return 0

    if args.check:
        print(f"[MISSING] {MODEL_ID} 尚未收录")
        return 1

    version = package_version(target)
    if version != VERIFIED_PI_AI_VERSION:
        fail(
            f"pi-ai 版本为 {version}，不是已验证的 {VERIFIED_PI_AI_VERSION}；"
            "禁止盲目重放，请重新核对上游目录"
        )
    old = models.get("deepseek-v4-flash")
    if not isinstance(old, dict) or old.get("provider") != "opencode-go":
        fail("旧 DeepSeek V4 Flash 语义锚点失配，拒绝修改")

    backup = target.with_name(target.name + BACKUP_SUFFIX)
    if not backup.exists():
        shutil.copy2(target, backup)
        print(f"[BACKUP] {backup}")
    else:
        print(f"[BACKUP] 已存在，保留最早版本：{backup}")

    models[MODEL_ID] = expected_model()
    target.write_text(
        json.dumps(catalog, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
        newline="",
    )
    verify(load_json(target))
    print(f"[OK] 已新增 {MODEL_ID}（DeepSeek V4.1 Flash）")
    print("[OK] 自校验通过：协议、模态、费用、上下文、输出与思考档位")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
