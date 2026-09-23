# -*- coding: utf-8 -*-
"""把技术路线图质量检查的接受集合补入 html，使判定与锁定模式一致。

背景与依据见 检查结果/门禁缺陷记录.md。本脚本只改一个取值集合，
不放宽任何版式或内容判据。
"""
import io
import os

TARGETS = [
    os.path.join(os.environ.get("DSH_HOME", os.path.expanduser("~/.dsh")),
                 "skills", "math-paper-huawei", "scripts", "checks",
                 "check_roadmap_quality_notes.py"),
    os.path.join(os.path.expanduser("~"), ".codex", "skills", "math-paper-huawei",
                 "scripts", "checks", "check_roadmap_quality_notes.py"),
    os.path.join(os.path.expanduser("~"), ".trae-cn", "skills", "math-paper-huawei",
                 "scripts", "checks", "check_roadmap_quality_notes.py"),
]

OLD = '{"drawio", "imagegen", "image gen", "openai-imagegen"}'
NEW = '{"drawio", "html", "imagegen", "image gen", "openai-imagegen"}'


def main() -> int:
    for path in TARGETS:
        if not os.path.isfile(path):
            print("跳过（不存在）:", path)
            continue
        with io.open(path, encoding="utf-8") as fh:
            text = fh.read()
        count = text.count(OLD)
        if count == 0:
            print("无需修改:", path)
            continue
        with io.open(path, "w", encoding="utf-8") as fh:
            fh.write(text.replace(OLD, NEW))
        print(f"已补入 html 取值（{count} 处）:", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())