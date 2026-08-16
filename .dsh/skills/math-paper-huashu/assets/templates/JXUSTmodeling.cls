%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% 2026 年“华数杯”大学生数学建模竞赛 LaTeX 文档类
% 版式依据：2026 第七届华数杯竞赛论文 DOCX 模板
% 成稿参照：第六届 A/B/C 题优秀论文
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{JXUSTmodeling}[2026/08/07 v3.0 Huashu Cup 2026]

\LoadClass[oneside,a4paper,UTF8,zihao=-4]{ctexart}

% ---------- 字体与正文 ----------
\RequirePackage{fontspec}
\IfFontExistsTF{Times New Roman}{\setmainfont{Times New Roman}}{\setmainfont{texgyretermes-regular.otf}[BoldFont=texgyretermes-bold.otf,ItalicFont=texgyretermes-italic.otf,BoldItalicFont=texgyretermes-bolditalic.otf]}
\IfFontExistsTF{SimSun}{\setCJKmainfont[AutoFakeBold=true]{SimSun}}{\setCJKmainfont[AutoFakeBold=true]{FandolSong-Regular}}
\IfFontExistsTF{SimHei}{\setCJKsansfont[AutoFakeBold=true]{SimHei}}{\setCJKsansfont[AutoFakeBold=true]{FandolHei-Regular}}
\RequirePackage{unicode-math}
\IfFontExistsTF{Cambria Math}{\setmathfont{Cambria Math}}{\setmathfont{latinmodern-math.otf}}
\RequirePackage[
  UseMSWordMultipleLineSpacing,
  MSWordLineSpacingMultiple=1.0
]{zhlineskip}
\AtBeginDocument{\songti\zihao{-4}\setlength{\parindent}{2\ccwd}}
\newcommand{\paperstrong}[1]{{\heiti\bfseries #1}}

% ---------- 页面：A4，四边 2.5 cm ----------
\RequirePackage[top=2.5cm,bottom=2.5cm,left=2.5cm,right=2.5cm]{geometry}
\pagestyle{plain}

% ---------- 数学、图表与浮动体 ----------
\RequirePackage{amsmath,amssymb,esint,physics,siunitx}
\RequirePackage{graphicx}
\graphicspath{{figures/}{images/}{./}}
\RequirePackage{booktabs,tabularx,multirow,makecell,longtable,array}
\RequirePackage{caption,subcaption,float}
\RequirePackage[section]{placeins}
\RequirePackage{needspace}

\renewcommand{\leq}{\leqslant}
\renewcommand{\geq}{\geqslant}
\newcolumntype{Y}{>{\centering\arraybackslash}X}
\captionsetup{format=hang,labelsep=space,font={small},labelfont={bf}}
\captionsetup[sub]{labelformat=simple}
\renewcommand\thesubfigure{(\alph{subfigure})}
\renewcommand*{\textfraction}{0.05}
\renewcommand*{\topfraction}{0.9}
\renewcommand*{\bottomfraction}{0.8}
\renewcommand*{\floatpagefraction}{0.85}

% ---------- 标题层级 ----------
\ctexset{
  section={
    format={\zihao{4}\heiti\centering},
    name={,、},
    aftername={\hspace{0pt}},
    number=\chinese{section},
    beforeskip=1.0\baselineskip,
    afterskip=0.5\baselineskip
  },
  subsection={
    format={\zihao{-4}\heiti\raggedright},
    name={},
    aftername={\hspace{0.5em}},
    number={\arabic{section}.\arabic{subsection}},
    beforeskip=0.7\baselineskip,
    afterskip=0.3\baselineskip
  },
  subsubsection={
    format={\zihao{-4}\heiti\raggedright},
    name={},
    aftername={\hspace{0.5em}},
    number={\arabic{section}.\arabic{subsection}.\arabic{subsubsection}},
    beforeskip=0.5\baselineskip,
    afterskip=0.2\baselineskip
  },
  appendix={name={附录,：},number=\Alph{section}}
}

% ---------- 列表 ----------
\RequirePackage{enumitem}
\setlist[enumerate,1]{
  leftmargin=0pt,
  labelsep=0pt,
  itemindent=3\ccwd+0.2cm,
  parsep=0pt,
  itemsep=0pt,
  topsep=0pt,
  partopsep=0pt,
  listparindent=2\ccwd
}
\def\labelenumi{\theenumi、}
\setlist[itemize,1]{
  leftmargin=0pt,
  itemindent=3\ccwd,
  parsep=0pt,
  itemsep=0pt,
  topsep=0pt,
  partopsep=0pt,
  listparindent=2\ccwd
}

% ---------- 引用、代码与链接 ----------
\RequirePackage{natbib}
\setcitestyle{square,super}
\RequirePackage{xcolor,listings}
\lstset{
  frame=single,
  breaklines=true,
  showstringspaces=false,
  basicstyle=\small\ttfamily,
  flexiblecolumns=true,
  keywordstyle=\color{blue},
  stringstyle=\color[rgb]{0.75,0,0.75},
  commentstyle=\songti\color[rgb]{0,0.5,0},
  tabsize=2
}
\RequirePackage{hyperref}
\hypersetup{hidelinks,bookmarksnumbered=true,bookmarksopen=true,pdfstartview=Fit}

% ---------- 华数杯首页信息接口 ----------
\makeatletter
\def\@biaoti{[论文标题]}
\def\@keyword{[关键词1]；[关键词2]；[关键词3]}
\def\@suoshuleibie{[本科组/研究生组/专科组]}
\def\@cansaibianhao{CM******}
\def\@saishimingcheng{2026年“华数杯”大学生数学建模竞赛}

\newcommand{\biaoti}[1]{\gdef\@biaoti{#1}}
\newcommand{\keyword}[1]{\gdef\@keyword{#1}}
\newcommand{\suoshuleibie}[1]{\gdef\@suoshuleibie{#1}}
\newcommand{\cansaibianhao}[1]{\gdef\@cansaibianhao{#1}}
\newcommand{\saishimingcheng}[1]{\gdef\@saishimingcheng{#1}}

\newcommand{\makehuashuheader}{%
  \begingroup
  \setlength{\tabcolsep}{3pt}%
  \renewcommand{\arraystretch}{1.45}%
  \noindent\begin{tabularx}{\textwidth}{|>{\centering\arraybackslash}p{2.9cm}|Y|>{\centering\arraybackslash}p{2.5cm}|}
    \hline
    所属类别 & \multirow{2}{=}{\centering\heiti\zihao{4}\bfseries\@saishimingcheng} & 参赛编号 \\
    \cline{1-1}\cline{3-3}
    \@suoshuleibie & & \@cansaibianhao \\
    \hline
  \end{tabularx}
  \par
  \endgroup
}

% 摘要环境自动生成官方首页抬头、标题、摘要标题和关键词。
\renewenvironment{abstract}{%
  \makehuashuheader
  \vspace{0.75cm}
  \begin{center}\heiti\zihao{3}\@biaoti\end{center}
  \vspace{0.35cm}
  \begin{center}\heiti\zihao{4}摘\quad 要\end{center}
  \vspace{0.2cm}
  \songti\zihao{-4}
  \setlength{\parindent}{2\ccwd}
}{%
  \par\vspace{0.6\baselineskip}
  \noindent{\heiti\bfseries 关键词：}\@keyword
  \label{abstract:end}
  \newpage
}

% ---------- 参考文献与附录 ----------
\renewcommand{\refname}{参考文献}
\AtBeginEnvironment{thebibliography}{%
  \phantomsection
  \addcontentsline{toc}{section}{参考文献}
  \songti\zihao{-4}
}

\newenvironment{appendixx}{%
  \clearpage
  \appendix
  \ctexset{section={format={\zihao{-4}\heiti\raggedright}}}
  \begingroup\centering\heiti\zihao{4}附\quad 录\par\endgroup
  \vspace{0.5\baselineskip}
  \zihao{-4}
}{}
\makeatother

\labelformat{figure}{图~#1}
\labelformat{table}{表~#1}
\labelformat{equation}{(#1)~式}
