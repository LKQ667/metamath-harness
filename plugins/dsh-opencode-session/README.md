# OpenCode 会话头修复

本项目原创的本地兼容插件（0.1.0），不引入第三方源码或素材。
对应官方问题：https://github.com/deepseek-ai/deepseek-harness/discussions/5495 。

DSH 0.1.2-rc.1 没有公开动态请求头接口，因此在进程内包装 PiAiAdapter.streamWithSnapshot 私有方法；以精确版本和函数 SHA-256 双重门禁限制使用。没有改写官方包或全局 fetch。
每次仅复制当前调用的 profile 与 headers，把 options.sessionId 写入 x-opencode-session；覆盖 OpenCode 原生路由及实际模型端点主机为 opencode.ai 的自定义路由。模型与凭据解析仍走官方实现，不读取或持久化凭据。
聊天、标题、压缩及重试共用该适配器入口；不依赖模型协议，不使用固定会话 ID，缺少有效 ID 时在本地拒绝。

构建：`npm run build`。测试：`npm test`；真实适配器测试需设置 `DSH_PI_AI_ENTRY` 为当前宿主 dsh-llm-pi-ai/lib/index.js 的绝对路径。
Profile 以 file: 依赖及 bundle 自激活；主 patch 无改动。没有 HTTP 路由、工具、Credentials scope、UI、自动下载或轮询。

回滚：移除 Profile bundles 中 dsh-opencode-session，重启；彻底移除可再移除 dependencies 并 pnpm install。保留用户会话与设置。
升级：先停用或重新验证精确版本、函数指纹、协议传输与并发测试；上游已正确发送稳定会话头时移除此插件。不得仅放宽版本门。file: 副本刷新遵循维护范式的 remove/add 和哈希比对流程。
