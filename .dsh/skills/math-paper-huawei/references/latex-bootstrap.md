# Windows LaTeX 自动自举

## 支持边界

- 正式支持具备宋体、黑体、Times New Roman、Cambria Math 的简体中文 Windows 10/11。
- 不分发微软字体，不静默替换字体，不修改系统级 PATH。
- 运行时必须位于项目交付目录之外，优先使用项目所在的非 C 盘 ASCII 缓存目录。

## 执行

step0 只做无网络快速探测：

```powershell
python <技能目录>\scripts\latex\latex_runtime.py probe --project <项目根目录>
```

探测缺失时只记录 `deferred_install`，不下载、不创建运行时目录，也不阻断 step1–step3。step4 首次草稿编译前运行 `latex_runtime.py compile`，届时按固定顺序处理：复用宿主 `latexmk + XeLaTeX`、复用托管运行时、使用已校验离线包、轮换官方 CTAN 镜像安装 TeX Live。自举使用用户级目录；仅当不存在合格非 C 盘时才回退 C 盘。

可用 `MATH_PAPER_CN_RUNTIME` 指定项目外的 ASCII 运行时目录；可用 `MATH_PAPER_CN_TEXLIVE_OFFLINE` 指定离线包。文件名、版本、镜像和最低空间由 `assets/latex/runtime-manifest.json` 统一定义。

## 验证与恢复

- 下载必须通过官方 SHA-512 或离线包 SHA-256 校验。
- 使用 `assets/latex/texlive.profile` 安装最小够用的中文、数学、图表、算法和 `latexmk` 包集。
- 编译缺包时只通过 `tlmgr` 定位并补齐，再重试。
- doctor 必须实际编译含四种指定字体的中文烟雾文档，并确认 PDF、LOG、AUX 均生成。
- 单个镜像失败时自动轮换；网络完全不可用时使用缓存或同发行版离线包。
- 每个配置镜像在单轮安装中最多尝试一次；失败后写入报告并结束本轮，禁止在网络、空间、权限和离线包条件未变化时循环重装。
- 字体缺失、磁盘不足、题目附件缺失等不可恢复条件必须写入报告并保留续跑点，禁止伪造成功。
