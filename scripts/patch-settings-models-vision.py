#!/usr/bin/env python3
"""识图开关热补丁：对官方全局包 dsh-client-ui-settings-models/lib/client.js 重打
GOAL-53 语义的"识图（图片输入）"复选框（0.1.2-rc.1 压缩产物结构）。

用法：
    python scripts/patch-settings-models-vision.py            # 打补丁（幂等）
    python scripts/patch-settings-models-vision.py --check    # 只检查状态不改文件

行为：
    - 幂等：文件已含 modelVision 时报告"已打过"并退出 0
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
    """按 npm 全局安装约定（%APPDATA%\\npm）定位官方 client.js。"""
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise SystemExit("无法定位 npm 全局目录：环境变量 APPDATA 未设置；"
                         "请用 DSH_SETTINGS_MODELS_CLIENT 显式指定目标文件。")
    return (Path(appdata) / "npm" / "node_modules" / "@deepseek-ai" / "dsh"
            / "node_modules" / "@deepseek-ai" / "dsh-client-ui-settings-models"
            / "lib" / "client.js")


DEFAULT_CLIENT = Path(
    os.environ.get(
        "DSH_SETTINGS_MODELS_CLIENT",
        str(_default_client()),
    )
)
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
        "t() 调用计数": source.count('t("modelVision")') == 2
        and source.count('t("modelVisionHint")') == 1,
    }
    bad = [name for name, ok in checks.items() if not ok]
    if bad:
        fail(f"自校验失败：{ '；'.join(bad) }")


def main() -> int:
    parser = argparse.ArgumentParser(description="识图开关热补丁（幂等重放）")
    parser.add_argument("--check", action="store_true", help="只检查状态，不修改文件")
    parser.add_argument("target", nargs="?", default=str(DEFAULT_CLIENT), help="client.js 路径")
    args = parser.parse_args()

    target = Path(args.target)
    if not target.is_file():
        fail(f"目标文件不存在：{target}")
    source = target.read_text(encoding="utf-8")

    if "modelVision" in source:
        print("[OK] 识图开关补丁已在位（modelVision 存在），无需重打")
        return 0

    if args.check:
        print("[MISSING] 识图开关补丁未打（modelVision 不存在）")
        return 1

    backup = target.with_name(target.name + BACKUP_SUFFIX)
    if not backup.exists():
        shutil.copy2(target, backup)
        print(f"[BACKUP] {backup}")
    else:
        print(f"[BACKUP] 已存在备份，保留最早版本：{backup}")

    patched = patch_jsx(source)
    patched = patch_locale(patched, ANCHOR_ZH, ZH_LOCALE_ADD, "zh")
    patched = patch_locale(patched, ANCHOR_EN, EN_LOCALE_ADD, "en")

    target.write_text(patched, encoding="utf-8", newline="")
    verify(target.read_text(encoding="utf-8"))
    print(f"[OK] 识图开关补丁已打：{target}")
    print("[OK] 自校验通过：zh/en 文案、复选框 JSX、input 写入语义全部在位")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
