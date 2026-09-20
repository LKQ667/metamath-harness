"""测试包标记。

tests/ 需要作为可导入包存在，因为部分用例会跨模块复用辅助函数，例如
`tests/test_final_template_selection.py` 中的
`from tests.test_candidate_matching import _catalog, _requirement`。
缺少本文件时，这类导入会抛出 ModuleNotFoundError。
"""
