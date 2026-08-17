# DSH 皮肤插件 · dsh-client-ui-skins v0.1.9

给 DeepSeek Harness (DSH) Web 界面换肤：4 套内置皮肤 + 自定义图片皮肤
（图片作为整个界面的背景，配色自动跟随图片主色调）。

## 效果预览

自定义图片皮肤支持任意 PNG / JPG / WebP：导入自己的图片后，背景、强调色与交互高亮会自动跟随图片主色调。以下仅为界面效果示例。

![DSH 自定义皮肤效果示例 1](assets/screenshots/mint-forest-dsh.jpg)

![DSH 自定义皮肤效果示例 2](assets/screenshots/ocean-guardian-dsh.jpg)

![DSH 自定义皮肤效果示例 3](assets/screenshots/crimson-moon-dsh.jpg)

## 文件

| 文件 | 作用 |
| --- | --- |
| `dsh-client-ui-skins-0.1.9.tgz` | 插件安装包（npm tarball） |
| `install-dsh-skins.sh` | 一键安装脚本 |
| `uninstall-dsh-skins.sh` | 一键卸载脚本 |

## 安装（二选一）

### 方式 A：一键脚本（推荐）
```bash
bash install-dsh-skins.sh
```
脚本会自动：装包 → 注册 → 重启。完成后刷新 `http://127.0.0.1:3080`，
左下角 **设置 → 通用设置 → 皮肤** 即可换肤。

### 方式 B：手动
```bash
# 1. 装包
cd ~/.dsh/profiles/web && pnpm add -w ./dsh-client-ui-skins-0.1.9.tgz

# 2. 注册（编辑 ~/.dsh/profiles/web/cordis.patch.yml，追加：）
#    - insert:
#        - id: ui-skins
#          name: 'dsh-client-ui-skins'

# 3. 重启 web
launchctl kickstart -k gui/$(id -u)/com.deepseek.dsh.web
```
其实你也可以直接扔给DeepSeek harness自己安装。
## 卸载
```bash
bash uninstall-dsh-skins.sh
```

## 备注
- 插件是纯 client 插件，不改任何 DSH 源码；卸载后完全恢复原生外观。
- 自定义皮肤图片只在本机流转（localStorage），不会上传到任何服务器。
- 需要 DSH web profile（`~/.dsh/profiles/web`），依赖 pnpm。
