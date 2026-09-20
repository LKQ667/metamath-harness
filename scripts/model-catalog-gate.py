#!/usr/bin/env python3
"""模型目录门禁（GOAL-79 / TASK-012）：DeepSeek 直连渠道本地 llm-deepseek 覆盖的
官方吸收退役 + 过期临时 ID 拒绝（分渠道）。

用法：
    python scripts/model-catalog-gate.py --check                    # 只检查不改文件
    python scripts/model-catalog-gate.py --retire                   # 官方已吸收时退役本地覆盖
    可选：--settings <settings.yaml>   （默认 F:\\DeepSeekHarness\\.dsh\\settings.yaml）
          --official-catalog <lib/index.js>  （默认从 %APPDATA%\\npm 全局安装解析）
          --opencode-catalog <models.json>   （OpenCode Go 官方 /models 抓取件，交叉核对）

行为（失败关闭）：
    - llm-deepseek 节内出现禁用 ID（deepseek-v4.1-flash、deepseek-v4.1-flash-expires-on-0910、
      任何含 expires-on 的 ID）→ check/retire 均失败退出 1（这些 ID 不是直连渠道官方名，
      deepseek-v4.1-flash 仅存在于 OpenCode Go 渠道官方目录）。
    - --retire：仅当 llm-deepseek.models 存在、无禁用 ID、且每个模型 ID 都被
      官方 dsh-llm-deepseek DEFAULT_MODELS 收录时，才整块移除 llm-deepseek 节
      （连同紧邻上方的关联注释行）；否则拒绝并说明原因。
    - 移除为文本级手术（不重排用户 YAML），写前备份 .bak-model-gate，写后自校验：
      YAML 可解析、其余顶层键与原值深度相等、llm-deepseek 已消失。
    - 遗留别名（deepseek-v4-flash / deepseek-v4-flash-vision-exp，2026-09-15 官方文档
      注明模型已退役但仍接受、由 V4.1 Flash 服务）仅提示，不拦截。
    - --opencode-catalog：对 llm-pi-ai.providers 中 baseURL 指向 opencode.ai/zen 的
      provider 逐模型核对官方目录；不在目录的 ID 记 WARNING（渠道目录随官方更新，
      不做硬失败），供人工决定是否清理。

官方证据（分渠道，2026-09-15 抓取）：
    - DeepSeek 直连 api-docs.deepseek.com：现行官方 ID deepseek-flash、deepseek-v4-pro；
      deepseek-v4-flash / deepseek-v4-flash-vision-exp 为退役别名（仍接受）。
    - OpenCode Go https://opencode.ai/zen/go/v1/models：37 个官方 ID，
      含 deepseek-v4.1-flash（该渠道有效名，与直连渠道不同）。
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import shutil
import sys
from pathlib import Path

import yaml

# ---- DeepSeek 直连渠道禁用 ID（分渠道；OpenCode Go 渠道不适用本名单） ----
BANNED_DIRECT_IDS = {
    "deepseek-v4.1-flash",                    # 非直连渠道官方名（仅 OpenCode Go 渠道收录）
    "deepseek-v4.1-flash-expires-on-0910",    # 已过期内测 ID
}
BANNED_PATTERN = re.compile(r"expires-on", re.IGNORECASE)
# 遗留别名：官方文档（2026-09-15）注明模型已退役、ID 仍被接受并由 V4.1 Flash 服务
LEGACY_ALIAS_IDS = {"deepseek-v4-flash", "deepseek-v4-flash-vision-exp"}
BACKUP_SUFFIX = ".bak-model-gate"


def fail(message: str) -> None:
    print(f"[FAIL] {message}", file=sys.stderr)
    raise SystemExit(1)


def default_settings() -> Path:
    override = os.environ.get("DSH_MODEL_GATE_SETTINGS")
    if override:
        return Path(override)
    return Path(__file__).resolve().parent.parent / ".dsh" / "settings.yaml"


def default_official_catalog() -> Path:
    """定位官方 dsh-llm-deepseek lib/index.js，兼容 0.1.2 内嵌与 0.1.5+ 提升两种布局。"""
    override = os.environ.get("DSH_MODEL_GATE_CATALOG")
    if override:
        return Path(override)
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise SystemExit("无法定位 npm 全局目录：APPDATA 未设置；请用 --official-catalog 指定。")
    npm_root = Path(appdata) / "npm" / "node_modules"
    tail = Path("@deepseek-ai") / "dsh-llm-deepseek" / "lib" / "index.js"
    candidates = [
        npm_root / "@deepseek-ai" / "dsh" / "node_modules" / tail,  # 0.1.2-rc.1 内嵌布局
        npm_root / tail,                                            # 0.1.5+ 提升布局
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[1]


def extract_official_ids(catalog_js: Path) -> list[str]:
    """从官方 dsh-llm-deepseek lib/index.js 的 DEFAULT_MODELS 块提取模型 ID。

    锚点：`const DEFAULT_MODELS = [` … 首个 `];`；块内逐个 `id: "..."`。
    任一锚点失配 → 失败关闭（官方构建结构变化需人工重新适配）。
    """
    source = catalog_js.read_text(encoding="utf-8")
    start = source.find("const DEFAULT_MODELS = [")
    if start == -1:
        fail(f"锚点失配：{catalog_js} 中未找到 DEFAULT_MODELS 块（官方结构已变化，需人工适配）")
    end = source.find("];", start)
    if end == -1:
        fail("锚点失配：DEFAULT_MODELS 块未闭合")
    ids = re.findall(r'id:\s*"([^"]+)"', source[start:end])
    if not ids:
        fail("锚点失配：DEFAULT_MODELS 块内未提取到任何模型 ID")
    return ids


def find_block_range(lines: list[str], key: str) -> tuple[int, int]:
    """返回顶层 key 块的 [起始行, 结束行)（含紧邻上方的连续注释行）。

    结束行 = 下一个顶层键行（列 0 的 `xxx:`）或文件末尾。
    """
    start = None
    for i, line in enumerate(lines):
        if line.rstrip("\r\n") == f"{key}:" or line.rstrip("\r\n").startswith(f"{key}:"):
            start = i
            break
    if start is None:
        fail(f"未找到顶层键 `{key}:`")
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if re.match(r"^[A-Za-z0-9_][A-Za-z0-9_.-]*:", lines[j]):
            end = j
            break
    # 向上收编紧邻的连续注释行（属于本块的说明）
    first = start
    while first > 0 and lines[first - 1].lstrip().startswith("#"):
        first -= 1
    return first, end


def deep_equal(a, b) -> bool:
    return a == b


def main() -> int:
    parser = argparse.ArgumentParser(description="模型目录门禁（官方吸收退役 + 过期 ID 拒绝）")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="只检查状态，不修改文件")
    mode.add_argument("--retire", action="store_true", help="官方已收录时退役 llm-deepseek 本地覆盖")
    parser.add_argument("--settings", default=str(default_settings()), help="settings.yaml 路径")
    parser.add_argument("--official-catalog", default=str(default_official_catalog()),
                        help="官方 dsh-llm-deepseek lib/index.js 路径")
    parser.add_argument("--opencode-catalog", default=None,
                        help="OpenCode Go 官方 /models JSON 抓取件（交叉核对，可选）")
    args = parser.parse_args()

    settings_path = Path(args.settings)
    if not settings_path.is_file():
        fail(f"目标文件不存在：{settings_path}")
    catalog_path = Path(args.official_catalog)
    if not catalog_path.is_file():
        fail(f"官方目录源不存在：{catalog_path}（请用 --official-catalog 指定）")

    official_ids = extract_official_ids(catalog_path)
    print(f"[INFO] 官方 dsh-deepseek 目录（{catalog_path}）：{', '.join(official_ids)}")

    original_text = settings_path.read_text(encoding="utf-8")
    try:
        original = yaml.safe_load(original_text)
    except yaml.YAMLError as e:
        fail(f"settings.yaml 解析失败：{e}")
    if not isinstance(original, dict):
        fail("settings.yaml 顶层不是映射")

    section = original.get("llm-deepseek")
    if section is None:
        print("[OK] llm-deepseek 本地覆盖不存在（已退役或从未配置），直连渠道采用官方目录")
        retired = True
        model_ids: list[str] = []
    else:
        retired = False
        models = section.get("models") if isinstance(section, dict) else None
        model_ids = [m.get("id", "") for m in (models or [])]
        if not model_ids:
            print("[WARN] llm-deepseek 节存在但 models 为空")

    # ---- 禁用 ID 检查（DeepSeek 直连渠道） ----
    banned_hits = [i for i in model_ids if i in BANNED_DIRECT_IDS or BANNED_PATTERN.search(i)]
    if banned_hits:
        fail(f"llm-deepseek.models 含禁用/过期 ID：{', '.join(banned_hits)}"
             "（直连渠道官方名为 deepseek-flash / deepseek-v4-pro；"
             "deepseek-v4.1-flash* 仅属 OpenCode Go 渠道）")

    legacy_hits = [i for i in model_ids if i in LEGACY_ALIAS_IDS]
    if legacy_hits:
        print(f"[INFO] 遗留别名（官方目录仍收录、模型已退役由 V4.1 Flash 服务）：{', '.join(legacy_hits)}")

    if retired:
        gate_ok = True
    else:
        uncovered = [i for i in model_ids if i not in official_ids]
        gate_ok = not uncovered
        if uncovered:
            print(f"[FAIL] llm-deepseek.models 存在官方目录未收录的 ID：{', '.join(uncovered)}；"
                  "拒绝退役（需人工确认是否为官方新增后再更新本门禁的官方目录源）", file=sys.stderr)

    # ---- OpenCode Go 渠道交叉核对（可选） ----
    if args.opencode_catalog:
        oc_path = Path(args.opencode_catalog)
        if not oc_path.is_file():
            fail(f"OpenCode 目录抓取件不存在：{oc_path}")
        oc_ids = {m["id"] for m in json.loads(oc_path.read_text(encoding="utf-8"))["data"]}
        pi = original.get("llm-pi-ai") or {}
        for name, provider in (pi.get("providers") or {}).items():
            base = str(provider.get("baseURL") or "")
            if "opencode.ai/zen" not in base:
                continue
            pids = [m.get("id", "") for m in (provider.get("models") or [])]
            if not pids:
                print(f"[INFO] provider `{name}`（{base}）未配置模型表——运行时经 llm-pi-ai "
                      "模型发现（GET /models）自动列出官方目录")
                continue
            stale = [i for i in pids if i not in oc_ids]
            if stale:
                print(f"[WARN] provider `{name}` 模型不在 OpenCode Go 官方目录（可能已改名/下架，"
                      f"供人工决定清理）：{', '.join(stale)}")
            else:
                print(f"[OK] provider `{name}` 全部 {len(pids)} 个模型均在 OpenCode Go 官方目录")

    # ---- 退役执行 ----
    if args.check:
        if not gate_ok:
            fail("检查未通过：见上方 [FAIL]")
        if retired:
            print("[OK] 门禁检查通过（无本地覆盖）")
        else:
            print(f"[MISSING] llm-deepseek 本地覆盖仍在位（{len(model_ids)} 模型："
                  f"{', '.join(model_ids)}）；官方目录已全部收录，可执行 --retire")
        return 0

    if retired:
        print("[OK] 无需退役（本地覆盖不存在）")
        return 0
    if not gate_ok:
        fail("退役被拒绝：见上方 [FAIL]")

    lines = original_text.splitlines(keepends=True)
    first, end = find_block_range(lines, "llm-deepseek")
    backup = settings_path.with_name(settings_path.name + BACKUP_SUFFIX)
    if not backup.exists():
        shutil.copy2(settings_path, backup)
        print(f"[BACKUP] {backup}")
    else:
        print(f"[BACKUP] 备份已存在，保留最早版本：{backup}")

    removed = "".join(lines[first:end])
    new_text = "".join(lines[:first]) + "".join(lines[end:])
    settings_path.write_text(new_text, encoding="utf-8", newline="")

    # ---- 写后自校验 ----
    try:
        after = yaml.safe_load(settings_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        fail(f"退役后 settings.yaml 解析失败（备份在 {backup}）：{e}")
    if "llm-deepseek" in after:
        fail("自校验失败：llm-deepseek 仍存在")
    expected_keys = set(original.keys()) - {"llm-deepseek"}
    if set(after.keys()) != expected_keys:
        fail(f"自校验失败：顶层键集合变化（期望 {sorted(expected_keys)}，实得 {sorted(after.keys())}）")
    for k in expected_keys:
        if not deep_equal(after.get(k), copy.deepcopy(original.get(k))):
            fail(f"自校验失败：顶层键 `{k}` 的值在退役中被改动")
    print(f"[OK] llm-deepseek 本地覆盖已退役（移除 {end - first} 行，含关联注释）")
    print("[OK] 自校验通过：YAML 可解析、其余全部顶层键值不变、llm-deepseek 已消失")
    print("[INFO] 直连渠道现在完整采用官方 dsh-llm-deepseek 目录："
          f"{', '.join(official_ids)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
