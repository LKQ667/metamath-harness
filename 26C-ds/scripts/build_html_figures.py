"""生成 12 张 HTML 论文示意图（HTML 矢量成图模式）。

风格族 A 朴素竞赛风（STYLE_FAMILY=0）：衬线字体、白底节点、直角 2px、无阴影、无副标题、
黑虚线分组框；强调色由 H0=210 推导（通用灰蓝，与论文既有蓝色调一致）。
造型旋钮：RADIUS=1(族内封顶 2px)、ARROW=3(chevron 分隔)、NODEACC=0(纯描边焦点)、SECT=1(细虚线框)。
布局旋钮 LAYOUT=3 → 等价范式取 ① 变体（横向流水线/分层堆叠/左右对照/矩阵网格）。

对齐纪律：并列结构一律用 display:grid + 等宽列（minmax(0,1fr) + min-width 锁总宽），
节点用统一宽度变量 --nw 保证等宽；节点不换行使 printToPDF 重新布局时尺寸完全确定。

运行：python scripts/build_html_figures.py
"""

from __future__ import annotations

import sys as _sys
_sys.dont_write_bytecode = True
try:
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
HAND = PROJECT / "手绘图"

CSS = """
html,body{margin:0;padding:0;width:fit-content;height:fit-content;background:transparent}
.fig,.fig *{font-family:"Times New Roman","SimSun","Songti SC","Microsoft YaHei",serif;
  box-sizing:border-box;-webkit-font-smoothing:antialiased}
.fig{width:fit-content;padding:20px 24px 30px;background:transparent;color:#111;
  --edge:#2b2b2b;--txt:#111;--line:#444;--muted:#555;
  --ac:hsl(210,42%,45%);--acbg:hsl(210,40%,95%);--no:#b0402f;--r:2px;
  --nw:170px;--gw:0px;font-size:15px;line-height:1.3}
.n{border:1px solid var(--edge);background:#fff;color:var(--txt);padding:9px 12px;
  font-size:15px;font-weight:500;text-align:center;border-radius:var(--r);
  white-space:nowrap;display:flex;align-items:center;justify-content:center;
  width:var(--nw);flex:0 0 auto}
.n.focus{border:1.6px solid var(--ac);background:var(--acbg);color:var(--ac);font-weight:700}
.n.dec{border:1.6px solid var(--ac);border-radius:3px;font-weight:600}
.grp{border:1.3px dashed var(--edge);border-radius:3px;padding:10px 13px;
  display:flex;flex-direction:column;gap:9px;align-items:center;justify-content:flex-start}
.grp>.gt{font-size:13px;font-weight:700;letter-spacing:1px}
.grp.acc{border-color:var(--ac)}
.col{display:flex;flex-direction:column;align-items:center;gap:0}
.row{display:flex;align-items:stretch;justify-content:center;gap:10px}
.grid{display:grid;gap:16px 24px;align-items:stretch;justify-items:stretch}
.g2{grid-template-columns:repeat(2,minmax(0,1fr));min-width:900px}
.g3{grid-template-columns:repeat(3,minmax(0,1fr));min-width:860px}
.g4{grid-template-columns:repeat(4,minmax(0,1fr));min-width:900px}
.span2{grid-column:span 2}
.span3{grid-column:span 3}
.chev{display:flex;align-items:center;justify-content:center;color:var(--line);
  font-size:17px;line-height:1;flex:0 0 18px;width:18px}
.chev.v{padding:1px 0}
.branch{display:flex;align-items:flex-start;justify-content:center;gap:34px}
.branch>.col{gap:0}
.lbl{font-size:13px;color:var(--line);padding:1px 0;text-align:center;white-space:nowrap}
.lbl.no{color:var(--no)}
.lbl.acc{color:var(--ac)}
.dn{display:flex;flex-direction:column;align-items:center}
.note{font-size:12.5px;color:var(--muted);text-align:center;white-space:nowrap}
"""


def page(title: str, body: str, fig_style: str = "") -> str:
    style = f' style="{fig_style}"' if fig_style else ""
    return (
        "<!DOCTYPE html>\n<html lang=\"zh-CN\">\n<head>\n<meta charset=\"utf-8\">\n"
        f"<title>{title}</title>\n<style>{CSS}</style>\n</head>\n<body>\n"
        f"<div class=\"fig\"{style}>\n{body}\n</div>\n</body>\n</html>\n"
    )


def n(text: str, cls: str = "") -> str:
    extra = f" {cls}" if cls else ""
    return f'<div class="n{extra}">{text}</div>'


def chev() -> str:
    return '<div class="chev">&#8250;</div>'


def chev_down() -> str:
    return '<div class="chev v">&#9662;</div>'


def hchain(items: list[str]) -> str:
    parts = []
    for index, item in enumerate(items):
        if index:
            parts.append(chev())
        parts.append(item)
    return '<div class="row">' + "".join(parts) + "</div>"


def grp(title: str, inner: str, style: str = "", acc: bool = False) -> str:
    cls = "grp acc" if acc else "grp"
    attr = f' style="{style}"' if style else ""
    head = f'<div class="gt">{title}</div>' if title else ""
    return f'<div class="{cls}"{attr}>{head}{inner}</div>'


FIGURES: dict[str, str] = {}
FIG_STYLE: dict[str, str] = {}

# ---------------------------------------------------------------- 1 技术路线图
FIG_STYLE["fig_roadmap"] = "--nw:212px"
FIGURES["fig_roadmap"] = page("技术路线图", f"""
<div class="grid g2">
  {grp("第一部分　数据解析、去噪与响应提取", f'''
    <div class="col" data-mh-col="1">
      {n("四份脑电记录")}
      {chev_down()}
      {n("事件解析与分段")}
      {chev_down()}
      {n("窄目标化去噪", "focus")}
      {chev_down()}
      {n("输出：干净脑电分段")}
      {chev_down()}
      {n("有效视觉响应提取")}
      {chev_down()}
      {n("三高斯分量拟合")}
      {chev_down()}
      {n("输出：响应曲线与偏侧指数")}
    </div>''')}
  {grp("第二部分　多尺度建模与认知验证", f'''
    <div class="col" data-mh-col="2">
      {n("LGN 时空滤波")}
      {chev_down()}
      {n("形状选择与除法归一化")}
      {chev_down()}
      {n("Wilson--Cowan 介观集群")}
      {chev_down()}
      {n("Kuramoto 同步与序参数")}
      {chev_down()}
      {n("头皮导联场观测")}
      {chev_down()}
      {n("左右区分特征", "focus")}
      {chev_down()}
      {n("双源认知宏观模型")}
      {chev_down()}
      {n("参数辨识与分层验证")}
    </div>''')}
  {grp("问题一产物", hchain([n("干净分段"), n("响应曲线"), n("偏侧指数")]),
       style="--nw:112px")}
  {grp("问题二与问题三产物", hchain([n("计算模型"), n("判别特征"), n("临床指标")]),
       style="--nw:112px")}
</div>
""", FIG_STYLE["fig_roadmap"])

# ---------------------------------------------------------------- 2 问题分析
FIG_STYLE["fig_problem_analysis"] = "--nw:150px"
FIGURES["fig_problem_analysis"] = page("问题分析流程图", f"""
<div class="grid g4" data-mh-col="1">
  {n("视觉刺激")}
  {n("视网膜与 LGN")}
  {n("皮层形状区")}
  {n("头皮三导观测")}
</div>
<div style="height:14px"></div>
<div class="grid g3">
  <div class="col">{chev_down()}<div class="lbl acc">问题一</div>{n("去噪与响应提取")}</div>
  <div class="col">{chev_down()}<div class="lbl acc">问题二</div>{n("机理与区分特征")}</div>
  <div class="col">{chev_down()}<div class="lbl acc">问题三</div>{n("认知模型与分析")}</div>
</div>
""", FIG_STYLE["fig_problem_analysis"])

# ---------------------------------------------------------------- 3 实验设计
FIG_STYLE["fig_experiment_design"] = "--nw:150px"
FIGURES["fig_experiment_design"] = page("实验设计与数据结构", f"""
<div class="grid g2">
  {grp("项目一　提示阶段已知目标位置", f'''
    {hchain([n("鼠标置于圆圈"), n("视觉提示指向"), n("等待目标出现"), n("点击目标")])}
    <div class="note">提示与应答方向一致率 1.000 / 0.980</div>''', style="--nw:148px;grid-column:span 2")}
  {grp("项目二　提示阶段只知目标形状", f'''
    {hchain([n("鼠标置于圆圈"), n("视觉提示形状"), n("等待左右目标"), n("点击对应三角")])}
    <div class="note">提示与应答方向一致率 0.470 / 0.480</div>''', style="--nw:148px;grid-column:span 2")}
  {grp("采集点位", hchain([n("F3 左额"), n("Fz 中线"), n("F4 右额")]), style="--nw:110px")}
  {grp("十通道语义", hchain([n("三导原始信号"), n("设备滤波"), n("ECG 参考"), n("事件与时间戳")]),
       style="--nw:104px")}
</div>
""", FIG_STYLE["fig_experiment_design"])

# ---------------------------------------------------------------- 4 伪迹来源
FIG_STYLE["fig_artifact_sources"] = "--nw:168px"
FIGURES["fig_artifact_sources"] = page("数据质量与伪迹来源分析", f"""
<div class="grid g3" data-mh-col="1">
  {n("设备量程饱和")}
  {n("运动与电极瞬变")}
  {n("心电与慢电位伪迹")}
  <div class="col">{chev_down()}<div class="lbl">不可修复</div></div>
  <div class="col">{chev_down()}<div class="lbl acc">本文处理</div></div>
  <div class="col">{chev_down()}<div class="lbl">先核验</div></div>
  {n("剔除饱和采样点")}
  {n("稳健软截断", "focus")}
  {n("相关度不足则不扣除")}
  {grp("四类来源与处理取舍", hchain([n("幅值削顶"), n("尖峰瞬变"), n("心搏同步波形"), n("低频慢电位：保留", "focus")]),
       style="--nw:152px;grid-column:span 3")}
</div>
""", FIG_STYLE["fig_artifact_sources"])

# ---------------------------------------------------------------- 5 Q1 去噪流程
FIG_STYLE["fig_q1_denoise_flow"] = "--nw:196px"
FIGURES["fig_q1_denoise_flow"] = page("窄目标化去噪流程", f"""
<div class="grid g3" data-mh-col="1">
  {n("基线校正与 R 波定位")}
  {n("心电三重条件筛选", "dec")}
  {n("稳健软截断 10 倍尺度", "focus")}
</div>
<div style="height:12px"></div>
<div class="branch">
  <div class="col"><div class="lbl acc">三条件同时满足</div>{chev_down()}{n("模板扣除", "dec")}</div>
  <div class="col"><div class="lbl no">任一条件不满足</div>{chev_down()}{n("保留原波形")}</div>
</div>
<div class="note" style="margin-top:10px">全流程不设高通或带通，低频慢电位完整保留</div>
""", FIG_STYLE["fig_q1_denoise_flow"])

# ---------------------------------------------------------------- 6 Q1 响应流程
FIG_STYLE["fig_q1_response_flow"] = "--nw:176px"
FIGURES["fig_q1_response_flow"] = page("有效视觉响应提取与曲线拟合流程", f"""
{hchain([
    n("逐点单样本 t 检验"),
    n("BH 错误发现率控制"),
    n("P300 峰值与潜伏期"),
    n("三高斯分量拟合"),
    n("偏侧指数", "focus"),
])}
""", FIG_STYLE["fig_q1_response_flow"])

# ---------------------------------------------------------------- 7 Q2 多尺度模型
FIG_STYLE["fig_q2_multiscale_model"] = "--nw:190px"
FIGURES["fig_q2_multiscale_model"] = page("多尺度前向计算模型", f"""
<div class="grid" style="grid-template-columns:1fr;min-width:660px;gap:12px">
  {grp("微观与介观：毫秒级到百毫秒级",
       hchain([n("LGN 时空滤波"), n("形状选择与归一化"), n("Wilson--Cowan 集群")]),
       style="--nw:176px")}
  {grp("宏观与观测：秒级",
       hchain([n("Kuramoto 同步与序参数"), n("头皮导联场观测", "focus")]),
       style="--nw:176px")}
</div>
<div class="note" style="margin-top:10px">尺度递进：毫秒级 &#8594; 十毫秒级 &#8594; 百毫秒级 &#8594; 秒级</div>
""", FIG_STYLE["fig_q2_multiscale_model"])

# ---------------------------------------------------------------- 8 Q2 镜像机制
FIG_STYLE["fig_q2_laterality_mechanism"] = "--nw:236px"
FIGURES["fig_q2_laterality_mechanism"] = page("左右三角刺激皮层响应镜像分布形成机制", f"""
<div class="row" data-mh-col="1">
  {n("右指三角源分布")}{chev()}{n("水平镜像")}{chev()}{n("左指三角源分布")}
</div>
<div style="height:14px"></div>
<div class="grid g2" style="min-width:620px">
  <div class="col"><div class="lbl">中线导联</div>{n("Fz：两侧贡献相消", "focus")}</div>
  <div class="col"><div class="lbl">偏侧导联</div>{n("F3 与 F4 权重互换", "focus")}</div>
</div>
<div style="height:10px"></div>
<div class="col">
  {chev_down()}
  {n("差分 F4 &#8722; F3 对镜像差异最敏感", "focus")}
</div>
""", FIG_STYLE["fig_q2_laterality_mechanism"])

# ---------------------------------------------------------------- 9 Q2 特征流程
FIG_STYLE["fig_q2_feature_flow"] = "--nw:236px"
FIGURES["fig_q2_feature_flow"] = page("形状与空间联合特征的构造与判别流程", f"""
<div class="grid g2" style="min-width:600px">
  {n("早期窗 80--250 ms 的 Fz 幅值")}
  {n("晚期窗 250--800 ms 的 F4 &#8722; F3")}
</div>
<div style="height:10px"></div>
<div class="row">
  <div class="chev v">&#9662;</div><div class="chev v">&#9662;</div>
</div>
<div style="height:6px"></div>
{hchain([n("联合特征向量"), n("线性判别分析"), n("左右判据", "focus")])}
""", FIG_STYLE["fig_q2_feature_flow"])

# ---------------------------------------------------------------- 10 Q3 模型框架
FIG_STYLE["fig_q3_model_framework"] = "--nw:212px"
FIGURES["fig_q3_model_framework"] = page("双源认知宏观模型框架", f"""
<div class="grid g2" style="min-width:640px">
  {n("LGN 与皮层视觉通路")}
  {n("海马体与前额记忆通路")}
</div>
<div class="col">
  <div class="lbl">双源并列</div>
  {chev_down()}
  {n("延迟耦合与前额整合", "focus")}
  {chev_down()}
  {n("头皮导联观测")}
</div>
<div style="height:12px"></div>
<div class="grid" style="grid-template-columns:1fr;min-width:640px">
  {grp("关键参数与窗口", hchain([n("延迟 &#964;<sub>H</sub>"), n("增益 g<sub>H</sub>"),
                                 n("窗口终点：应答前 100 ms")]), style="--nw:186px")}
</div>
""", FIG_STYLE["fig_q3_model_framework"])

# ---------------------------------------------------------------- 11 Q3 辨识流程
FIG_STYLE["fig_q3_estimation_flow"] = "--nw:196px"
FIGURES["fig_q3_estimation_flow"] = page("认知模型参数辨识与分析流程", f"""
<div class="row">
  {n("认知窗口截取")}{chev()}{n("参数初始化与约束")}{chev()}{n("加权残差最小化")}
</div>
<div class="col" style="margin:8px 0">
  {chev_down()}
</div>
<div class="row">
  {n("扰动扫描与可辨识性")}{chev()}{n("分层分析与对照", "focus")}
</div>
""", FIG_STYLE["fig_q3_estimation_flow"])

# ---------------------------------------------------------------- 12 Q3 应用
FIG_STYLE["fig_q3_application"] = "--nw:178px"
FIGURES["fig_q3_application"] = page("模型体系结构、评价与临床指标", f"""
<div class="row" data-mh-col="1">
  {n("双源认知宏观模型")}{chev()}{n("记忆回路强度 &#934;", "focus")}{chev()}
  {n("&#964;<sub>H</sub> 与 g<sub>H</sub> 趋势")}{chev()}{n("临床指标")}
</div>
<div style="height:16px"></div>
<div class="grid g3">
  <div class="col"><div class="lbl">局限</div>{n("增益弱可辨识")}</div>
  <div class="col"><div class="lbl">改进</div>{n("纵向与多被试样本")}</div>
  <div class="col"><div class="lbl">后续</div>{n("横断面数据不足")}</div>
</div>
""", FIG_STYLE["fig_q3_application"])


def main() -> int:
    HAND.mkdir(parents=True, exist_ok=True)
    for name, html in FIGURES.items():
        (HAND / f"{name}.html").write_text(html, encoding="utf-8")
    print(f"共写出 {len(FIGURES)} 张 HTML 图到 手绘图/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
