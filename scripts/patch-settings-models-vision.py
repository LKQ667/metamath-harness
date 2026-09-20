#!/usr/bin/env python3
"""识图开关热补丁：对官方全局包 dsh-client-ui-settings-models/lib/client.js 重打
GOAL-53 语义的"识图（图片输入）"复选框（0.1.2-rc.1 压缩产物结构）。

用法：
    python scripts/patch-settings-models-vision.py            # 打补丁（幂等）
    python scripts/patch-settings-models-vision.py --check    # 只检查状态不改文件

行为：
    - 幂等：已含 modelVision 时完整自校验，残缺状态非零退出
    - 锚点：语义稳定的 JSX/locale 结构（非行号）；任一锚点失配 → 非零退出
    - 自校验：写回后重读，断言注入计数；备份 client.js.bak-hotfix-vision
    - 目标文件可用环境变量 DSH_SETTINGS_MODELS_CLIENT 覆盖（测试用）
    - 目标路径默认从 APPDATA 动态解析 npm 全局目录，无硬编码用户路径

适用场景：DSH 官方包升级覆盖安装产物后，设置页"自定义提供方 → 模型行 →
容量"折叠区的"识图（图片输入）"复选框会随旧产物一起丢失；重跑本脚本即可恢复。
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path


def _default_client() -> Path:
    """按 npm 全局安装约定（%APPDATA%\\npm）定位官方 client.js。

    支持两种布局：
    - DSH <= 0.1.2：包内嵌在 dsh 包下（dsh/node_modules/@deepseek-ai/...）
    - DSH >= 0.1.5：包被提升到顶层（node_modules/@deepseek-ai/...）
    优先返回真实存在的那一份；都不存在时返回 0.1.5 布局以便报错信息指向当前结构。
    """
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise SystemExit("无法定位 npm 全局目录：环境变量 APPDATA 未设置；"
                         "请用 DSH_SETTINGS_MODELS_CLIENT 显式指定目标文件。")
    npm_root = Path(appdata) / "npm" / "node_modules"
    tail = Path("@deepseek-ai") / "dsh-client-ui-settings-models" / "lib" / "client.js"
    candidates = [
        npm_root / "@deepseek-ai" / "dsh" / "node_modules" / tail,   # 0.1.2-rc.1 内嵌布局
        npm_root / tail,                                             # 0.1.5+ 提升布局
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[1]


def default_client() -> Path:
    """显式覆盖无需依赖 APPDATA；延迟解析以支持位置参数和离线测试。"""
    override = os.environ.get("DSH_SETTINGS_MODELS_CLIENT")
    return Path(override) if override else _default_client()
BACKUP_SUFFIX = ".bak-hotfix-vision"

# ---- 注入内容（缩进为 tab，与官方压缩产物一致） ----

# 识图复选框：追加在模型行"容量"折叠区 maxTokens label 之后（pi-ai 自定义
# 提供方 ModelListEditor，patch/editCapacity 作用域）。勾选 input:[text,image]，
# 取消 input:void 0（继承 defaultInput）——与 GOAL-53 语义逐字一致。
VISION_LABEL_JSX = (
    ", (0, react_jsx_runtime.jsxs)(\"label\", {\n"
    "\t\t\t\t\t\t\t\tclassName: ModelsSection_module_css_default[\"modelField\"],\n"
    "\t\t\t\t\t\t\t\tchildren: [(0, react_jsx_runtime.jsx)(\"span\", {\n"
    "\t\t\t\t\t\t\t\t\tclassName: ModelsSection_module_css_default[\"modelFieldLabel\"],\n"
    "\t\t\t\t\t\t\t\t\tchildren: t(\"modelVision\")\n"
    "\t\t\t\t\t\t\t\t}), (0, react_jsx_runtime.jsx)(\"input\", {\n"
    "\t\t\t\t\t\t\t\t\ttype: \"checkbox\",\n"
    "\t\t\t\t\t\t\t\t\tchecked: Array.isArray(model.input) && model.input.includes(\"image\"),\n"
    "\t\t\t\t\t\t\t\t\ttitle: t(\"modelVisionHint\"),\n"
    "\t\t\t\t\t\t\t\t\t\"aria-label\": `${t(\"modelVision\")} ${index + 1}`,\n"
    "\t\t\t\t\t\t\t\t\tdisabled,\n"
    "\t\t\t\t\t\t\t\t\tonChange: (event) => {\n"
    "\t\t\t\t\t\t\t\t\t\tpatch(index, event.target.checked ? { input: [\"text\", \"image\"] } : { input: void 0 });\n"
    "\t\t\t\t\t\t\t\t\t}\n"
    "\t\t\t\t\t\t\t\t})]\n"
    "\t\t\t\t\t\t\t})"
)

ZH_LOCALE_ADD = (
    "\n\t\t\tmodelVision: \"识图（图片输入）\",\n"
    "\t\t\tmodelVisionHint: \"勾选后该模型接受图片输入\","
)
EN_LOCALE_ADD = (
    "\n\t\t\tmodelVision: \"Vision (image input)\",\n"
    "\t\t\tmodelVisionHint: \"When checked, this model accepts image input\","
)

# ---- 锚点（官方 0.1.2-rc.1 压缩产物中各唯一） ----

ANCHOR_MAXTOKENS = 'editCapacity(index, "maxTokens", event.target.value);'
ANCHOR_ZH = 'modelAdvanced: "容量",'
ANCHOR_EN = 'modelAdvanced: "Capacities",'


def fail(message: str) -> None:
    print(f"[FAIL] {message}", file=sys.stderr)
    raise SystemExit(1)


def patch_jsx(source: str) -> str:
    """在 maxTokens label 完整闭合后追加识图复选框。

    锚点结构（tab 缩进）：
        editCapacity(index, "maxTokens", event.target.value);
        {9t}}          <- onChange 闭
        {8t}})]        <- input 闭 + label children 数组闭   （第一个 })]）
        {7t}})]        <- label 闭 + modelAdvanced 数组闭     （注入点在 }后 ]前）
    """
    idx = source.find(ANCHOR_MAXTOKENS)
    if idx == -1:
        fail(f"锚点失配：未找到 `{ANCHOR_MAXTOKENS}`（官方构建结构已变化，需人工重新适配）")
    # 第一个 })]：input 闭 + label children 数组闭
    first = source.find("})", idx + len(ANCHOR_MAXTOKENS))
    if first == -1:
        fail("锚点失配：maxTokens label 内部闭合未找到")
    # 第二个 })：label 完整闭（其后紧跟 modelAdvanced children 数组闭 ]）
    second = source.find("})", first + 2)
    if second == -1 or source[second + 2 : second + 3] != "]":
        fail("锚点失配：maxTokens label 完整闭合序列异常（期望 `})]`）")
    insert_at = second + 2
    return source[:insert_at] + VISION_LABEL_JSX + source[insert_at:]


def patch_locale(source: str, anchor: str, addition: str, lang: str) -> str:
    idx = source.find(anchor)
    if idx == -1:
        fail(f"锚点失配：未找到 {lang} locale `{anchor}`")
    line_end = source.find("\n", idx)
    if line_end == -1:
        fail(f"锚点失配：{lang} locale 锚点行无换行结尾")
    return source[: line_end + 1] + addition.lstrip("\n") + "\n" + source[line_end + 1 :]


def verify(source: str) -> None:
    """写回后自校验：注入物逐项在位。"""
    checks = {
        "zh 文案 modelVision": source.count('modelVision: "识图（图片输入）"') == 1,
        "en 文案 modelVision": source.count('modelVision: "Vision (image input)"') == 1,
        "复选框判定逻辑": source.count('model.input.includes("image")') == 1,
        "勾选写入 input": source.count('{ input: ["text", "image"] }') == 1,
        "取消恢复继承": source.count('event.target.checked ? { input: ["text", "image"] } : { input: void 0 }') == 1,
        "完整复选框 JSX": source.count(VISION_LABEL_JSX) == 1,
        "zh 提示文案": source.count('modelVisionHint: "勾选后该模型接受图片输入"') == 1,
        "en 提示文案": source.count('modelVisionHint: "When checked, this model accepts image input"') == 1,
        "t() 调用计数": source.count('t("modelVision")') == 2
        and source.count('t("modelVisionHint")') == 1,
    }
    bad = [name for name, ok in checks.items() if not ok]
    if bad:
        fail(f"自校验失败：{ '；'.join(bad) }")


def main() -> int:
    parser = argparse.ArgumentParser(description="识图开关热补丁（幂等重放）")
    parser.add_argument("--check", action="store_true", help="只检查状态，不修改文件")
    parser.add_argument("target", nargs="?", help="client.js 路径")
    args = parser.parse_args()

    target = Path(args.target) if args.target else default_client()
    if not target.is_file():
        fail(f"目标文件不存在：{target}")
    source = target.read_text(encoding="utf-8")

    if "modelVision" in source:
        verify(source)
        print("[OK] 识图开关完整补丁已在位，自校验通过，无需重打")
        return 0

    if args.check:
        print("[MISSING] 识图开关补丁未打（modelVision 不存在）")
        return 1

    # 先生成并校验，锚点失配或残缺候选不得修改目标/备份。
    patched = patch_jsx(source)
    patched = patch_locale(patched, ANCHOR_ZH, ZH_LOCALE_ADD, "zh")
    patched = patch_locale(patched, ANCHOR_EN, EN_LOCALE_ADD, "en")
    verify(patched)

    backup = target.with_name(target.name + BACKUP_SUFFIX)
    if not backup.exists():
        shutil.copy2(target, backup)
        print(f"[BACKUP] {backup}")
    else:
        print(f"[BACKUP] 已存在备份，保留最早版本：{backup}")

    target.write_text(patched, encoding="utf-8", newline="")
    verify(target.read_text(encoding="utf-8"))
    print(f"[OK] 识图开关补丁已打：{target}")
    print("[OK] 自校验通过：zh/en 文案、复选框 JSX、input 写入语义全部在位")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
