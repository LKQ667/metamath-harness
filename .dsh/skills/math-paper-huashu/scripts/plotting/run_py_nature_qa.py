from __future__ import annotations

import argparse
from pathlib import Path

from py_nature_core import run_py_nature_qa


def main() -> int:
    parser = argparse.ArgumentParser(description="运行 Py-Nature 图像 QA")
    parser.add_argument("target", help="输出基础路径，或带扩展名的具体文件")
    args = parser.parse_args()

    result = run_py_nature_qa(Path(args.target))
    for key, value in result.checks.items():
        print(f"{key}: {value}")
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
