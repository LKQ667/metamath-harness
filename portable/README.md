# DeepSeek Harness 便携版维护说明

支持 Windows 10/11 x64。解压后双击根目录的 `启动-DeepSeek-Harness.cmd`；首次启动会从只读模板初始化 `data/dsh-home/`。在线模型仍需接收者填写自己的合法 API Key。

## 构建与发布

在开发工作区运行 `构建便携版.ps1`。构建前需有至少 20 GB 可用空间；这只是下载、解压、staging 和 ZIP 复测的临时峰值保护，不会给接收者预占 20 GB。目标解压体积为 4–7 GB，7–8 GB 会生成最大组件报告，超过 8 GB 拒绝发布。

构建器固定并核验 Node、DSH、Python、Python 包、Draw.io、Poppler 和 TeX Live 来源，先在 staging 完成依赖自检、秘密与绝对路径扫描、链接检查和 ZIP 解压复测；全部通过后才写入正式 `dist/`。

## 更新与回滚

保留 `data/`，只在独立 staging 下载并校验新的 `app/` 或 `runtime/`。先运行 `依赖自检.cmd` 和完整验收，再替换旧目录；失败时丢弃 staging，继续使用上一份可用版本。不要复制旧 `node_modules` 覆盖新版，也不要覆盖 `data/dsh-home/`。

发行清单见根目录 `RELEASE-MANIFEST.json`。它记录版本、来源、SHA-256、许可证、相对安装位置和体积。微软字体不随包分发；系统缺字时模板回退到 Fandol、TeX Gyre Termes 和 Latin Modern Math。
