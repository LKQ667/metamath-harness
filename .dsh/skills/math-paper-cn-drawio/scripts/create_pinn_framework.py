#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""按提示词4生成六区多尺度 PINN 科研框架图。"""
from pathlib import Path
import json
import xml.etree.ElementTree as ET

ROOT = Path(r"F:\数学建模论文skills\math-paper-cn-drawio\绘图结果\多尺度PINN框架")
FONT = "html=1;whiteSpace=wrap;fontFamily=Microsoft YaHei;fontSize=13;fontColor=#1F2937;"
COLORS={"blue":("#EAF3F8","#3775BA"),"purple":("#F2EDF8","#7653A6"),"green":("#EEF6EA","#4F8A4B"),"orange":("#FFF4E6","#D97706"),"gray":("#F6F7F9","#64748B")}
CN={'sys':'复杂动力系统<br><font color="#64748B">生物 · 气候 · 材料 · 社会网络</font>','eq':'数学抽象<br><b>dx/dt = f(x,t;θ)</b><br>∂u/∂t = F(u,∇u,∇²u;θ)','var':'外部驱动 u(t)<br>状态 x(t) · 参数 θ','macro':'宏观尺度<br>种群动力学 X(t)','meso':'中观尺度<br>网络交互 Aᵢⱼ','micro':'微观尺度<br>分子 / 智能体 xᵢ(t)','gov':'多尺度控制方程<br><b>dx/dt = F(x,θ)</b><br>∂u/∂t + N(u)=0','net':'物理信息神经网络<br><font color="#64748B">(x,t) → 神经表征 → uθ(x,t)</font>','data':'数据损失<br>Ldata = ||u_pred-u_obs||²','pde':'物理损失<br>Lpde = ||∂u/∂t-F(u)||²','bc':'边界损失<br>Lbc = ||u(x,t)-g(x)||²','total':'总目标函数<br><b>Ltotal = λ₁Ldata + λ₂Lpde + λ₃Lbc</b>','opt':'参数优化引擎<br>梯度下降 · 贝叶斯优化 · MCMC','theta':'θ → θ*<br>扩散 · 反应 · 耦合','uq':'不确定性量化<br>置信区间 · 分布 · 灵敏度','sim':'数值求解器 → 预测场','heat':'热力图<br>u(x,t)','phase':'相图<br>动力学吸引子','network':'网络演化<br>预测','pred':'模型预测','obs':'实验观测','err':'误差分析<br>E=||Y模型-Y实验||','update':'参数更新<br>模型迭代','legend':'图例<br>实线：信息流 · 双向：耦合 · 虚线：反馈'}

CN.update({'p1':'真实复杂系统','p2':'多尺度数学建模','p3':'物理信息神经网络','p4':'参数优化与不确定性','p5':'模型预测与计算模拟','p6':'实验验证与反馈闭环','data':'数据损失<br>L数据 = ||û-u观测||²','pde':'物理损失<br>L物理 = ||∂u/∂t-F(u)||²','bc':'边界损失<br>L边界 = ||u(x,t)-g(x)||²','total':'总目标函数<br><b>L总 = λ₁L数据 + λ₂L物理 + λ₃L边界</b>','opt':'参数优化引擎<br>梯度下降 · 贝叶斯优化 · 马尔可夫链蒙特卡洛'})

def main():
    hand=ROOT/'手绘图'; fig=ROOT/'figures'; hand.mkdir(parents=True,exist_ok=True); fig.mkdir(parents=True,exist_ok=True)
    mf=ET.Element('mxfile',{'host':'app.diagrams.net'}); dg=ET.SubElement(mf,'diagram',{'id':'pinn','name':'Multiscale PINN'}); m=ET.SubElement(dg,'mxGraphModel',{'page':'1','pageWidth':'1920','pageHeight':'1080','grid':'1','defaultFontFamily':'Arial'}); r=ET.SubElement(m,'root'); ET.SubElement(r,'mxCell',{'id':'0'}); ET.SubElement(r,'mxCell',{'id':'1','parent':'0'})
    boxes={}
    def box(i,label,x,y,w,h,kind='blue',shape='rounded=1;'):
        fill,stroke=COLORS[kind]; style=f'{shape}{FONT}fillColor={fill};strokeColor={stroke};strokeWidth=1.5;'; c=ET.SubElement(r,'mxCell',{'id':i,'value':CN.get(i,label),'style':style,'vertex':'1','parent':'1'}); ET.SubElement(c,'mxGeometry',{'x':str(x),'y':str(y),'width':str(w),'height':str(h),'as':'geometry'}); boxes[i]=(x,y,w,h)
    def edge(i,s,t,label='',dash=False,bi=False):
        style=f'edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;fontFamily=Arial;fontSize=11;strokeColor=#52606D;endArrow=classic;endFill=1;'
        if dash: style+='dashed=1;dashPattern=6 6;'
        if bi: style+='startArrow=classic;startFill=1;'
        c=ET.SubElement(r,'mxCell',{'id':i,'value':label,'style':style,'edge':'1','parent':'1','source':s,'target':t}); ET.SubElement(c,'mxGeometry',{'relative':'1','as':'geometry'})
    def panel(i,title,x,y,w,h): box(i,title,x,y,w,34,'gray')
    panel('p1','1  Physical System Layer',30,100,260,720); panel('p2','2  Multiscale Mathematical Model',320,100,270,720); panel('p3','3  Physics-Informed Neural Network',620,100,360,720); panel('p4','4  Optimization & Uncertainty',1010,100,260,720); panel('p5','5  AI-enhanced Simulation',1300,100,260,720); panel('p6','6  Validation Feedback Loop',1590,100,270,720)
    box('sys','Complex dynamical system<br><font color="#64748B">biological · climate · material · social</font>',55,165,210,82,'blue'); box('eq','Mathematical abstraction<br><b>dx/dt = f(x,t;θ)</b><br>∂u/∂t = F(u,∇u,∇²u;θ)',55,285,210,102,'purple'); box('var','External forcing u(t)<br>State x(t) · Parameters θ',55,430,210,65,'gray')
    box('macro','Macro-scale<br>Population dynamics X(t)',350,175,205,62,'blue'); box('meso','Meso-scale<br>Network interaction Aᵢⱼ',350,285,205,62,'blue'); box('micro','Micro-scale<br>Molecular / agent xᵢ(t)',350,395,205,62,'blue'); box('gov','Multiscale governing equations<br><b>dx/dt = F(x,θ)</b><br>∂u/∂t + N(u)=0',350,520,205,88,'purple')
    box('net','Physics-Informed Neural Network<br><font color="#64748B">(x,t) → neural representation → uθ(x,t)</font>',650,175,300,100,'green'); box('data','Data loss<br>Ldata = ||u_pred-u_obs||²',650,325,140,70,'blue'); box('pde','Physics loss<br>Lpde = ||∂u/∂t-F(u)||²',810,325,140,70,'purple'); box('bc','Boundary loss<br>Lbc = ||u(x,t)-g(x)||²',730,425,140,70,'orange'); box('total','Total objective<br><b>Ltotal = λ₁Ldata + λ₂Lpde + λ₃Lbc</b>',665,545,270,68,'green')
    box('opt','Optimization engine<br>Gradient descent · Bayesian optimization · MCMC',1040,190,200,82,'orange'); box('theta','θ → θ*<br>diffusion · reaction · coupling',1040,320,200,65,'purple'); box('uq','Uncertainty quantification<br>confidence interval · distribution · sensitivity',1040,440,200,82,'blue')
    box('sim','Numerical solver → Prediction field',1330,190,200,65,'green'); box('heat','Heat map<br>u(x,t)',1330,320,90,70,'blue'); box('phase','Phase portrait<br>dynamic attractor',1440,320,90,70,'purple'); box('network','Network evolution<br>forecast',1385,430,95,70,'orange')
    box('pred','Model prediction',1620,180,210,55,'green'); box('obs','Experimental observation',1620,285,210,55,'blue'); box('err','Error analysis<br>E=||Ymodel-Yexperiment||',1620,390,210,65,'purple'); box('update','Parameter updating<br>Model refinement',1620,510,210,65,'orange'); box('legend','Legend<br>— information flow · ⇄ coupling · - - feedback',1620,665,210,65,'gray')
    for a,b in [('sys','eq'),('eq','macro'),('micro','gov'),('gov','net'),('data','total'),('pde','total'),('net','total'),('total','opt'),('opt','theta'),('theta','uq'),('uq','sim'),('sim','heat'),('sim','phase'),('sim','network'),('sim','pred'),('pred','obs'),('obs','err'),('err','update')]: edge('e'+a+b,a,b)
    edge('ecouple1','macro','meso','尺度耦合',bi=True); edge('ecouple2','meso','micro','时空传递',bi=True); edge('efeed','update','net','反馈调节',dash=True)
    out=hand/'多尺度PINN科研框架.drawio'; out.write_bytes(b'<?xml version="1.0" encoding="UTF-8"?>\n'+ET.tostring(mf,encoding='utf-8'))
    manifest={'figures':[{'id':'multiscale-pinn','title':'Framework of a physics-informed multiscale mathematical modeling system','purpose':'模型总体框架图','section':'模型建立','source':'手绘图/多尺度PINN科研框架.drawio','exports':['手绘图/多尺度PINN科研框架.png','手绘图/多尺度PINN科研框架.svg'],'paper_ready':True,'checks':['xml','layout','visual-round-1','visual-round-2'],'export_status':'ok','needs_visual_review':False}]}; (fig/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__': main()
