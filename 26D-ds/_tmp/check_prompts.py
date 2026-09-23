# -*- coding: utf-8 -*-
"""概念图提示词硬性要求自查（一次性校验脚本，写入 _tmp 供本次交付使用）。"""
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

FILES = [
    "手绘图/原理图-运输能耗构成.md",
    "手绘图/机制图-中继通信保障.md",
    "手绘图/示意图-任务分区与资源缺口.md",
]
POLL = ["禁止编造", "禁止造假", "结果复核", "三轮复核", "不得抄袭", "可复现", "可信输出"]
VAGUE = ["美观大气", "高级感", "科技感", "丰富细节", "随意发挥"]
META = ["布局原型：", "阅读方向：", "主色家族：", "区分点："]
EXPECT_H2 = ["## 服务段落", "## 生成图片的提示词", "## 硬约束"]
EXACT = "仅借鉴形式，不复制具体内容、数据、标签、结论"

ok = True
metavals = {m: [] for m in META}


def check(label, cond, extra=""):
    global ok
    print("  [%s] %s %s" % ("OK" if cond else "FAIL", label, extra))
    if not cond:
        ok = False
    return cond


for f in FILES:
    t = open(f, encoding="utf-8").read()
    lines = t.split("\n")
    print("=" * 72)
    print(f)

    h2 = [l for l in lines if re.match(r"^##\s", l)]
    h1 = [l for l in lines if re.match(r"^#\s", l) and not l.startswith("##")]
    h3 = [l for l in lines if re.match(r"^#{3,}\s", l)]
    check("恰好 3 个 H2 且名称完全一致", h2 == EXPECT_H2, str(h2))
    check("无 H1", not h1, str(h1))
    check("无 H3 及更深标题", not h3, str(h3))

    def sec(name):
        m = re.search(r"^## " + re.escape(name) + r"[ \t]*\n(.*?)(?=\n## |\Z)", t, re.M | re.S)
        return m.group(1) if m else ""

    s1, s2, s3 = sec("服务段落"), sec("生成图片的提示词"), sec("硬约束")

    print(" -- 服务段落 --")
    check("放置位置类词", bool(re.search(r"用于论文.*(章节|段落|位置)", s1)))
    check("依据类词", bool(re.search(r"依据|来自|基于|根据", s1)))
    check("知识方法类词", bool(re.search(r"知识|方法|模型|原理|机制", s1)))

    print(" -- 生成图片的提示词 --")
    rel = [w for w in ["输入", "机制", "输出", "关系", "路径", "状态", "约束"] if w in s2]
    check("关系类词（≥1，实际全含）", len(rel) >= 1, str(rel))
    check("含 参考图组", "参考图组" in s2)
    check("含 assets/reference-pictures/", "assets/reference-pictures/" in s2)
    five = [w for w in ["框架", "结构", "排版", "思维链", "配色"] if w in s2]
    check("含 借鉴点", "借鉴点" in s2)
    check("含 框架/结构/排版/思维链/配色 五词", len(five) == 5, str(five))
    check("含形式借鉴声明原文", EXACT in s2)
    for m in META:
        mm = re.search(re.escape(m) + r"(.+)", s2)
        v = mm.group(1).strip() if mm else None
        check("元信息 " + m, bool(v), str(v))
        if v:
            metavals[m].append(v)

    print(" -- 全文禁词 --")
    check("无污染词", not [w for w in POLL if w in t], str([w for w in POLL if w in t]))
    check("无空泛词", not [w for w in VAGUE if w in t], str([w for w in VAGUE if w in t]))

    print(" -- 硬约束 --")
    check("写明不生成图片/只保留提示词", bool(re.search(r"不生成图片|只保留提示词", s3)))
    check("写明图内不出现英文水印", "英文水印" in s3)

print("=" * 72)
print("=== 四项元信息跨文件两两不同 ===")
for m in META:
    vals = metavals[m]
    uniq = len(set(vals))
    print("  [%s] %s -> %d 个不同取值" % ("OK" if uniq == 3 else "FAIL", m, uniq))
    for v in vals:
        print("         ", v)
    if uniq != 3:
        ok = False

print("=" * 72)
print("TOTAL:", "ALL PASS" if ok else "HAS FAILURES")
sys.exit(0 if ok else 1)
