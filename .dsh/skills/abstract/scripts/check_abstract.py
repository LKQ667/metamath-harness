#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
国赛数学建模摘要合规性与质量自动化质检器 (check_abstract.py)
用于离线检测摘要的字数区间、单页铺满度、零独立公式约束、针对问题X加粗规范及反 AI 腔调。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List


BANNED_AI_WORDS = [
    "革命性", "颠覆性", "令人瞩目", "极其优异", "十分显著",
    "显而易见", "众所周知", "不难看出", "不言而喻", "由此可知",
    "显著提升了鲁棒性", "显著提高了泛化", "极具推广价值", "成果斐然",
]

SEQUENTIAL_WORDS = ["首先", "其次", "然后", "接着", "最后"]


def strip_latex_and_markdown(text: str) -> str:
    """提取纯文本内容用于字符计数"""
    # 移除 LaTeX 注释 (避免将正文百分比数字如 99% 误判为注释导致截断整行)
    clean = re.sub(r"^\s*%.*$", "", text, flags=re.MULTILINE)
    # 移除 LaTeX 格式命令，保留参数内容
    clean = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?\{([^}]*)\}", r"\1", clean)
    # 移除独立 LaTeX 命令
    clean = re.sub(r"\\[a-zA-Z]+", "", clean)
    # 移除 Markdown 加粗与斜体
    clean = re.sub(r"[*_]{1,3}([^*_]+)[*_]{1,3}", r"\1", clean)
    # 移除 Markdown 标签
    clean = re.sub(r"^#+\s+.*$", "", clean, flags=re.MULTILINE)
    # 移除空白字符
    clean = re.sub(r"\s+", "", clean)
    return clean


def count_chinese_chars(text: str) -> int:
    """统计纯汉字字符数量"""
    clean_text = strip_latex_and_markdown(text)
    chinese_chars = re.findall(r"[\u4e00-\u9fff]", clean_text)
    return len(chinese_chars)


def check_standalone_equations(text: str) -> List[str]:
    """检测是否存在独立公式环境 (绝对禁止)"""
    violations = []
    # 先剔除 LaTeX 注释内容，防止注释里的说明文字引起误判
    clean_code = re.sub(r"^\s*%.*$", "", text, flags=re.MULTILINE)

    # 检测 LaTeX equation / align / gather / displaymath
    eq_envs = re.findall(r"\\begin\{(equation\*?|align\*?|gather\*?|displaymath\*?|multline\*?)\}", clean_code)
    if eq_envs:
        violations.extend([f"LaTeX 独立公式环境 \\begin{{{env}}}" for env in eq_envs])
    
    # 检测 $$...$$
    if "$$" in clean_code:
        violations.append("Markdown/LaTeX 独立展示公式 $$...$$")
        
    # 检测 \\[ ... \\]
    if re.search(r"\\\[.*?\\\]", clean_code, flags=re.DOTALL):
        violations.append("LaTeX 独立公式语法 \\[ ... \\]")
        
    return violations


def check_question_bolding(text: str) -> Dict[str, Any]:
    """检测针对问题X：是否加粗，且冒号是否一并加粗"""
    # 查找所有类似 "针对问题[一二三四五六七八九十1-9]" 的出现
    raw_patterns = re.findall(r"针对问题[一二三四五六七八九十1-90-9]+[：:,，]?", text)
    
    compliant = []
    non_compliant = []
    
    # 合规形式1: Markdown **针对问题X：**
    # 合规形式2: LaTeX \paperstrong{针对问题X：} 或 \textbf{针对问题X：}
    valid_md = re.findall(r"\*\*针对问题[一二三四五六七八九十1-90-9]+：\*\*", text)
    valid_tex_ps = re.findall(r"\\paperstrong\{针对问题[一二三四五六七八九十1-90-9]+：\}", text)
    valid_tex_tb = re.findall(r"\\textbf\{针对问题[一二三四五六七八九十1-90-9]+：\}", text)
    
    valid_matches = valid_md + valid_tex_ps + valid_tex_tb
    compliant.extend(valid_matches)
    
    # 检查是否有未合规的形态（如冒号在加粗外，或使用了逗号，或未加粗）
    for p in raw_patterns:
        # 如果不是标准 "针对问题X：" 且被包在加粗里
        normalized_target_md = f"**{p.rstrip('：:,，')}：**"
        normalized_target_ps = f"\\paperstrong{{{p.rstrip('：:,，')}：}}"
        normalized_target_tb = f"\\textbf{{{p.rstrip('：:,，')}：}}"
        if not any(target in text for target in (normalized_target_md, normalized_target_ps, normalized_target_tb)):
            non_compliant.append(p)
            
    return {
        "raw_found": raw_patterns,
        "compliant": compliant,
        "non_compliant": list(set(non_compliant)),
    }


def check_anti_ai(text: str) -> Dict[str, Any]:
    """检测 AI 腔调、机械顺承词及违禁套话"""
    found_banned = []
    for word in BANNED_AI_WORDS:
        if word in text:
            found_banned.append(word)
            
    found_seq = []
    for seq in SEQUENTIAL_WORDS:
        if seq in text:
            found_seq.append(seq)
            
    return {
        "banned_ai_words": found_banned,
        "sequential_words": found_seq,
        "is_sequential_excessive": len(found_seq) >= 2,
    }


def check_numerical_density(text: str) -> Dict[str, Any]:
    """检测数值结果与物理单位充实度"""
    # 匹配数字+常见物理量单位或纯高精度小数
    numbers = re.findall(r"\b\d+(?:\.\d+)?\s*(?:MW|kW/m²|kW/m\^2|m/s|km/h|m|s|min|h|%|海里|元)?\b", text)
    # 排除单字符数字，保留具备结果意义的数字
    meaningful_numbers = [n for n in numbers if len(n.strip()) > 1]
    return {
        "count": len(meaningful_numbers),
        "samples": meaningful_numbers[:8],
        "is_sufficient": len(meaningful_numbers) >= 3,
    }


def run_all_checks(text: str) -> Dict[str, Any]:
    """执行全部质检门禁"""
    char_count = count_chinese_chars(text)
    eq_violations = check_standalone_equations(text)
    bolding_res = check_question_bolding(text)
    ai_res = check_anti_ai(text)
    num_res = check_numerical_density(text)
    
    errors = []
    warnings = []
    
    # 1. 字数与版面检查 (850 ~ 1050 汉字)
    if char_count < 850:
        if char_count < 750:
            errors.append(f"有效汉字字数严重偏少 ({char_count}字 < 750字)，A4版面下半页会出现大面积留白，属于严重失分项！建议扩充至 850~1050 字。")
        else:
            warnings.append(f"有效汉字字数略偏少 ({char_count}字)，推荐黄金区间为 850~1050 字以达到 88%~93% 单页满铺。")
    elif char_count > 1050:
        if char_count > 1150:
            errors.append(f"有效汉字字数过多 ({char_count}字 > 1150字)，编译排版时必然跨到第 2 页，违反国赛单页摘要硬性约束！必须删减至 1050 字以内。")
        else:
            warnings.append(f"有效汉字字数偏多 ({char_count}字)，排版时有溢出到第 2 页风险，建议微调至 950~1020 字。")
            
    # 2. 独立公式检查 (零容忍)
    if eq_violations:
        for v in eq_violations:
            errors.append(f"严禁出现独立公式环境：{v}。摘要必须全部行内化，使用自然语言加行内数学符号。")
            
    # 3. 针对问题X：加粗检查
    if bolding_res["non_compliant"]:
        for item in bolding_res["non_compliant"]:
            errors.append(f"问题标签格式未规范加粗：'{item}'。规范要求必须连同冒号一起加粗（如 **针对问题一：** 或 \\paperstrong{{针对问题一：}}）。")
    elif not bolding_res["compliant"]:
        warnings.append("未检测到标准形式的 '针对问题X：' 加粗引导词，若本论文为多问赛题请确保逐问段首规范加粗。")
        
    # 4. 反 AI 语体检查
    if ai_res["banned_ai_words"]:
        for bw in ai_res["banned_ai_words"]:
            warnings.append(f"发现高频 AI 腔调/宣传空话词汇：'{bw}'，建议替换为客观机理或定量描述。")
            
    if ai_res["is_sequential_excessive"]:
        warnings.append(f"检测到多个死板顺承词：{ai_res['sequential_words']}。建议剔除，改用机理动词与非对称句式直接论述。")
        
    # 5. 数值结果充实度检查
    if not num_res["is_sufficient"]:
        warnings.append(f"检测到核心定量结果偏少（有效数据仅 {num_res['count']} 处），缺乏量化支撑。各问应明确给出最终收敛数值、指标或解坐标。")

    is_passed = len(errors) == 0
    
    return {
        "passed": is_passed,
        "char_count": char_count,
        "char_count_status": "optimal" if 850 <= char_count <= 1050 else ("low" if char_count < 850 else "high"),
        "errors": errors,
        "warnings": warnings,
        "equation_violations": eq_violations,
        "bolding_status": bolding_res,
        "anti_ai_status": ai_res,
        "numerical_density": num_res,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="国赛数学建模摘要质量合规检查器")
    parser.add_argument("--file", "-f", type=str, help="摘要源文件路径 (Markdown / LaTeX / TXT)")
    parser.add_argument("--text", "-t", type=str, help="直接传入摘要文本内容")
    parser.add_argument("--json", action="store_true", help="以 JSON 格式输出结果")
    args = parser.parse_args()

    content = ""
    if args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"错误：文件不存在 {file_path}", file=sys.stderr)
            return 1
        content = file_path.read_text(encoding="utf-8")
    elif args.text:
        content = args.text
    else:
        # 从标准输入读取
        if not sys.stdin.isatty():
            content = sys.stdin.read()
        else:
            parser.print_help()
            return 1

    result = run_all_checks(content)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("=" * 60)
        print("         国赛数学建模摘要质量与合规质检报告")
        print("=" * 60)
        status_str = "【通过 PASS】" if result["passed"] else "【未通过 FAIL】"
        print(f"质检结论：{status_str}")
        print(f"有效汉字字数：{result['char_count']} 字 (标准区间: 850 ~ 1050 字)")
        print(f"单页覆盖评估：{'黄金单页满铺 (88%~93%)' if result['char_count_status'] == 'optimal' else ('偏少易留白' if result['char_count_status'] == 'low' else '偏多易跨页')}")
        print(f"定量数值点数：{result['numerical_density']['count']} 处 (样例: {', '.join(result['numerical_density']['samples'][:4])})")
        print("-" * 60)

        if result["errors"]:
            print(f"【阻断性硬错误 ({len(result['errors'])} 项)】：")
            for i, err in enumerate(result["errors"], 1):
                print(f"  {i}. [ERR] {err}")
            print("-" * 60)

        if result["warnings"]:
            print(f"【优化改进建议 ({len(result['warnings'])} 项)】：")
            for i, warn in enumerate(result["warnings"], 1):
                print(f"  {i}. [WARN] {warn}")
            print("-" * 60)

    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
