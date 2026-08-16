from __future__ import annotations

import argparse
import runpy
import sys
from pathlib import Path

from template_registry import TEMPLATE_REGISTRY


def main() -> int:
    parser = argparse.ArgumentParser(description="运行 Py-Nature 模板示例")
    parser.add_argument("template", choices=sorted(TEMPLATE_REGISTRY.keys()))
    parser.add_argument("--output-dir", default="demo_output")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    template_file = root / "assets" / "templates" / f"{args.template}.py"
    if not template_file.exists():
        raise FileNotFoundError(template_file)

    sys.argv = [str(template_file), "--output-dir", str(Path(args.output_dir).resolve())]
    runpy.run_path(str(template_file), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
