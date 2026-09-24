"""把非数据绘图模式切换为 html，并归档原 Draw.io 源与导出。

用户已确认：12 张非数据图全部改为 HTML 出图（技术路线图内容与版式保持不变）。
运行：python scripts/switch_to_html_mode.py
"""

from __future__ import annotations

import sys as _sys
_sys.dont_write_bytecode = True
try:
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import json
import shutil
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
HAND = PROJECT / "手绘图"
ARCHIVE = PROJECT / "归档" / "drawio"
STATE = PROJECT / "项目状态.json"
MANIFEST = PROJECT / "figures" / "manifest.json"


def main() -> int:
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    moved = []
    for pattern in ("*.drawio", "*.svg", "*_brief.json", "*_labels.json", "中文最小验证.*"):
        for path in HAND.glob(pattern):
            if path.is_file():
                shutil.move(str(path), str(ARCHIVE / path.name))
                moved.append(path.name)
    tools = HAND / "_tools"
    if tools.is_dir():
        shutil.move(str(tools), str(ARCHIVE / "_tools"))
        moved.append("_tools/")
    print(f"已归档 {len(moved)} 个 Draw.io 源与辅助文件到 归档/drawio/")

    state = json.loads(STATE.read_text(encoding="utf-8"))
    state["drawing_mode"] = "html"
    state["drawing_mode_source"] = "user_override"
    state["drawing_mode_note"] = (
        "用户要求把非数据绘图改为 HTML 矢量成图；因门禁要求全项目统一一种非数据绘图模式，"
        "技术路线图一并转为 HTML，其内容与版式保持不变。原 Draw.io 源与导出归档于 归档/drawio/。"
    )
    state["locked_options"]["drawing_mode"] = "HTML矢量成图"
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest["drawing_mode"] = "html"
    manifest["drawing_mode_source"] = "user_override"
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print("项目状态与 manifest 顶层 drawing_mode 已切换为 html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
