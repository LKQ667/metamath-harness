[CmdletBinding()]
param([Parameter(Mandatory)][string]$Root, [string]$ModulePath)
$ErrorActionPreference = 'Stop'
$Root = [IO.Path]::GetFullPath($Root)
$runtime = Join-Path $Root 'runtime'
$python = Join-Path $runtime 'python\python.exe'
$xelatex = Join-Path $runtime 'texlive\bin\windows\xelatex.exe'
$drawio = Join-Path $runtime 'drawio\draw.io.exe'
$pdfinfo = Join-Path $runtime 'poppler\Library\bin\pdfinfo.exe'
$pdftoppm = Join-Path $runtime 'poppler\Library\bin\pdftoppm.exe'
$work = Join-Path $Root 'data\acceptance'
New-Item -ItemType Directory -Force -Path $work | Out-Null
$module = if ($ModulePath) { $ModulePath } else { Join-Path $Root 'portable\Portable.Common.psm1' }
Import-Module $module -Force
$env:PATH = ((Join-Path $runtime 'python'), (Join-Path $runtime 'python\Scripts'), (Get-ShortWindowsPath (Join-Path $runtime 'texlive\bin\windows')), (Join-Path $runtime 'poppler\Library\bin'), (Join-Path $runtime 'drawio'), (Join-Path $env:SystemRoot 'System32')) -join ';'
$env:DSH_RUNTIME_ROOT = $runtime
$env:DSH_PORTABLE_ROOT = $Root
$env:DSH_PORTABLE_STRICT = '1'
$xelatex = Get-ShortWindowsPath $xelatex
$toolWork = Join-Path (New-PortableAsciiAlias -Root $Root) 'data\acceptance'
$toolRuntime = Join-Path (New-PortableAsciiAlias -Root $Root) 'runtime'
$drawio = Join-Path $toolRuntime 'drawio\draw.io.exe'
$pdfinfo = Join-Path $toolRuntime 'poppler\Library\bin\pdfinfo.exe'
$pdftoppm = Join-Path $toolRuntime 'poppler\Library\bin\pdftoppm.exe'
$env:DRAWIO_CLI = $drawio
$env:MPLCONFIGDIR = Join-Path $work 'mpl'

$pythonCode = @'
import json, pathlib
import numpy as np, pandas as pd, scipy, matplotlib, sklearn, statsmodels.api as sm
import networkx as nx, sympy as sp, pypdf, fitz, pulp
from openpyxl import Workbook, load_workbook
from sklearn.linear_model import LinearRegression
root = pathlib.Path(r"__WORK__")
root.mkdir(parents=True, exist_ok=True)
frame = pd.DataFrame({"x":[1.,2.,3.],"y":[2.,4.,6.]})
frame.to_excel(root / "matrix.xlsx", index=False, engine="openpyxl")
assert load_workbook(root / "matrix.xlsx").active.max_row == 4
assert abs(LinearRegression().fit(frame[["x"]], frame["y"]).coef_[0]-2) < 1e-9
assert int(nx.shortest_path_length(nx.path_graph(4),0,3)) == 3
assert sp.integrate(sp.Symbol("x"), (sp.Symbol("x"),0,1)) == sp.Rational(1,2)
problem=pulp.LpProblem("portable",pulp.LpMinimize); x=pulp.LpVariable("x",lowBound=2); problem += x
assert problem.solve(pulp.PULP_CBC_CMD(msg=False)) == pulp.LpStatusOptimal and abs(x.value()-2)<1e-9
import matplotlib.pyplot as plt
plt.plot(frame.x, frame.y); plt.savefig(root / "matrix.png"); plt.close()
versions={name:__import__(name).__version__ for name in ["numpy","matplotlib","pandas","scipy","sklearn","statsmodels","networkx","sympy","pypdf","fitz","seaborn","pulp"]}
(root / "python-matrix.json").write_text(json.dumps(versions,ensure_ascii=False,indent=2),encoding="utf-8")
'@.Replace('__WORK__', ($work -replace '\\','\\'))
& $python -c $pythonCode
if ($LASTEXITCODE -ne 0) { throw 'Python/CBC 组件矩阵失败。' }

$drawioSource = Join-Path $toolWork 'portable.drawio'
'<mxfile><diagram><mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/><mxCell id="2" value="便携验收" vertex="1" parent="1"><mxGeometry x="20" y="20" width="160" height="60" as="geometry"/></mxCell></root></mxGraphModel></diagram></mxfile>' | Set-Content -LiteralPath $drawioSource -Encoding utf8
foreach ($format in @('png','svg','pdf')) {
    $output = Join-Path $toolWork "drawio.$format"
    $arguments = @('--export','--format',$format,'--output',$output,$drawioSource)
    $process = Start-Process -FilePath $drawio -ArgumentList $arguments -Wait -WindowStyle Hidden -PassThru
    if ($process.ExitCode -ne 0 -or -not (Test-Path $output) -or (Get-Item $output).Length -le 100) { throw "Draw.io $format 导出失败。" }
}

$latexCases = @(
    @{name='math-paper-cn'; preamble='\documentclass{article}\usepackage{ctex}\IfFontExistsTF{SimSun}{\setCJKmainfont{SimSun}}{\setCJKmainfont{FandolSong-Regular}}\IfFontExistsTF{Times New Roman}{\setmainfont{Times New Roman}}{\setmainfont{TeX Gyre Termes}}\usepackage{unicode-math}\IfFontExistsTF{Cambria Math}{\setmathfont{Cambria Math}}{\setmathfont{Latin Modern Math}}'},
    @{name='math-paper-huashu'; preamble='\documentclass{article}\usepackage{ctex}\usepackage{algorithm2e,physics,siunitx}\IfFontExistsTF{SimSun}{\setCJKmainfont{SimSun}}{\setCJKmainfont{FandolSong-Regular}}'},
    @{name='yatai-cn'; preamble='\documentclass{article}\usepackage{ctex}\IfFontExistsTF{Times New Roman}{\setmainfont{Times New Roman}}{\setmainfont{texgyretermes-regular.otf}}\usepackage{unicode-math}\setmathfont{latinmodern-math.otf}'}
)
foreach ($case in $latexCases) {
    $dir = Join-Path $toolWork $case.name; New-Item -ItemType Directory -Force -Path $dir | Out-Null
    $tex = "$($case.preamble)`n\begin{document}中文便携字体回退 \(E=mc^2\)\end{document}"
    Set-Content -LiteralPath (Join-Path $dir 'main.tex') -Value $tex -Encoding utf8
    $latexOutput = & $xelatex -interaction=nonstopmode -halt-on-error "-output-directory=$dir" (Join-Path $dir 'main.tex') 2>&1
    $latexExit = $LASTEXITCODE
    $latexOutput | Set-Content -LiteralPath (Join-Path $dir 'console.log') -Encoding utf8
    if ($latexExit -ne 0 -or -not (Test-Path (Join-Path $dir 'main.pdf'))) { throw "$($case.name) XeLaTeX 失败（exit=$latexExit）。" }
    & $pdfinfo (Join-Path $dir 'main.pdf') | Set-Content -LiteralPath (Join-Path $dir 'pdfinfo.txt') -Encoding utf8
    & $pdftoppm -f 1 -singlefile -png -r 72 (Join-Path $dir 'main.pdf') (Join-Path $dir 'page')
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path (Join-Path $dir 'page.png'))) { throw "$($case.name) Poppler 渲染失败。" }
}

[ordered]@{schema='dsh.portable.acceptance/v1'; status='pass'; root='.'; python='pass'; cbc='pass'; drawio=@('png','svg','pdf'); latex=@('math-paper-cn','math-paper-huashu','yatai-cn'); poppler='pass'} | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $work 'acceptance-report.json') -Encoding utf8
'Runtime acceptance：PASS'
