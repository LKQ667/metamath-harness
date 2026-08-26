#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""三列两行、无交叉连线的中文多尺度 PINN 框架图。"""
from pathlib import Path
import json
import xml.etree.ElementTree as E

ROOT=Path(r'F:\数学建模论文skills\math-paper-cn-drawio\绘图结果\多尺度PINN框架')
FONT='html=1;whiteSpace=wrap;fontFamily=Microsoft YaHei;fontSize=15;fontColor=#17212B;'
PA={'蓝':('#EAF3F8','#3C7FB1'),'绿':('#EEF7EC','#4C8B5A'),'紫':('#F3EEF9','#7B5AA6'),'橙':('#FFF4E5','#C87818'),'灰':('#F7F8FA','#718096')}

def main():
 h=ROOT/'手绘图'; f=ROOT/'figures'; h.mkdir(parents=True,exist_ok=True); f.mkdir(parents=True,exist_ok=True)
 mf=E.Element('mxfile',{'host':'app.diagrams.net'}); dg=E.SubElement(mf,'diagram',{'id':'clean-pinn','name':'多尺度PINN框架'}); m=E.SubElement(dg,'mxGraphModel',{'page':'1','pageWidth':'1600','pageHeight':'1050','grid':'1','defaultFontFamily':'Microsoft YaHei'}); r=E.SubElement(m,'root'); E.SubElement(r,'mxCell',{'id':'0'}); E.SubElement(r,'mxCell',{'id':'1','parent':'0'})
 def b(i,v,x,y,w=330,hh=72,k='蓝',fs=15):
  fill,stroke=PA[k]; c=E.SubElement(r,'mxCell',{'id':i,'value':v,'style':f'rounded=1;arcSize=12;{FONT}fontSize={fs};fillColor={fill};strokeColor={stroke};strokeWidth=1.6;','vertex':'1','parent':'1'}); E.SubElement(c,'mxGeometry',{'x':str(x),'y':str(y),'width':str(w),'height':str(hh),'as':'geometry'})
 def e(i,s,t,label='',dash=False):
  style='edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;fontFamily=Microsoft YaHei;fontSize=13;strokeColor=#52606D;strokeWidth=1.5;endArrow=classic;endFill=1;exitX=0.5;exitY=1;entryX=0.5;entryY=0;'
  if dash: style+='dashed=1;dashPattern=6 6;'
  c=E.SubElement(r,'mxCell',{'id':i,'value':label,'style':style,'edge':'1','parent':'1','source':s,'target':t}); E.SubElement(c,'mxGeometry',{'relative':'1','as':'geometry'})
 def title(i,v,x,y,w): b(i,v,x,y,w,38,'灰',17)
 title('t1','① 真实复杂系统',70,60,380); title('t2','② 多尺度数学建模',610,60,380); title('t3','③ 物理信息神经网络',1150,60,380)
 b('s1','复杂动力系统\n生物 · 气候 · 材料 · 社会网络',95,135,330,78,'蓝'); b('s2','数学抽象\n dx/dt = f(x,t;θ)\n ∂u/∂t = F(u,∇u,∇²u;θ)',95,265,330,100,'紫'); b('s3','外部驱动 u(t)  ·  状态 x(t)  ·  参数 θ',95,415,330,65,'灰')
 b('m1','宏观尺度：种群动力学 X(t)',635,135,330,62,'蓝'); b('m2','中观尺度：网络交互 Aᵢⱼ',635,235,330,62,'蓝'); b('m3','微观尺度：分子 / 智能体 xᵢ(t)',635,335,330,62,'蓝'); b('m4','多尺度控制方程\n dx/dt = F(x,θ)；∂u/∂t + N(u)=0',635,435,330,78,'紫')
 b('p1','输入 (x,t)  →  神经表征  →  输出 uθ(x,t)',1175,135,330,72,'绿'); b('p2','数据损失\nL数据 = ||û-u观测||²',1175,250,150,70,'蓝',14); b('p3','物理损失\nL物理 = ||∂u/∂t-F(u)||²',1355,250,150,70,'紫',14); b('p4','边界损失\nL边界 = ||u(x,t)-g(x)||²',1175,355,150,70,'橙',14); b('p5','总目标函数\nL总 = λ₁L数据 + λ₂L物理 + λ₃L边界',1355,355,150,70,'绿',13)
 title('t4','④ 参数优化与不确定性',70,590,380); title('t5','⑤ 模型预测与计算模拟',610,590,380); title('t6','⑥ 实验验证与反馈闭环',1150,590,380)
 b('o1','参数优化\n梯度下降 · 贝叶斯优化 · 马尔可夫链蒙特卡洛',95,665,330,82,'橙',14); b('o2','最优参数 θ*',95,790,330,62,'紫'); b('o3','不确定性量化\n置信区间 · 概率分布 · 灵敏度',95,890,330,72,'蓝',14)
 b('q1','数值求解器 → 预测场',635,665,330,70,'绿'); b('q2','热力图  u(x,t)',635,790,150,65,'蓝'); b('q3','相图：动力学吸引子',815,790,150,65,'紫'); b('q4','网络演化与预测',725,890,150,65,'橙')
 b('v1','模型预测',1175,665,330,60,'绿'); b('v2','实验观测',1175,765,330,60,'蓝'); b('v3','误差分析\nE = ||Y模型-Y实验||',1175,865,150,70,'紫',14); b('v4','参数更新\n模型迭代',1355,865,150,70,'橙',14)
 for x,y in [('s1','s2'),('s2','s3'),('m1','m2'),('m2','m3'),('m3','m4'),('p1','p2'),('p1','p3'),('p2','p4'),('p3','p5'),('p4','p5'),('o1','o2'),('o2','o3'),('q1','q2'),('q1','q3'),('q2','q4'),('v1','v2'),('v2','v3')]: e('e'+x+y,x,y)
 e('a1','s2','m1','系统建模'); e('a2','m4','p1','方程约束'); e('a3','p5','o1','参数学习'); e('a4','o3','q1','不确定性传播'); e('a5','q4','v1','预测结果'); e('a6','v3','v4','误差驱动'); e('a7','v4','o1','参数回传',True)
 out=h/'多尺度PINN科研框架.drawio'; out.write_bytes(b'<?xml version="1.0" encoding="UTF-8"?>\n'+E.tostring(mf,encoding='utf-8'))
 man={'figures':[{'id':'pinn-clean','title':'多尺度物理信息神经网络框架','purpose':'模型总体框架图','section':'模型建立','source':'手绘图/多尺度PINN科研框架.drawio','exports':['手绘图/多尺度PINN科研框架.png','手绘图/多尺度PINN科研框架.svg'],'paper_ready':False,'checks':['xml','layout','visual-round-1'],'export_status':'ok','needs_visual_review':True}]}; (f/'manifest.json').write_text(json.dumps(man,ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__': main()
