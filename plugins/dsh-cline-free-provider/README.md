# dsh-cline-free-provider

Cline Free provider for dsh.

[English](README.en.md)

本插件可以将 Cline 的免费模型，接入 dsh 使用。

<img height="650" alt="截图 2026-08-17 10-39-41" src="https://github.com/user-attachments/assets/849c8ca8-2f97-4603-898a-37598a2dede5" />

Cline 提供 OpenRouter 上可用的各种免费模型，以及 DeepSeek V4 Flash、GLM 5.3 Flash、Muse Spark 1.3。

如果你使用的是 Cline Pass 订阅计划，可以直接按照 Cline Pass 官方文档配置官方接口和 API Key，不需要本插件。

获取 API Key：<https://app.cline.bot/dashboard/account?tab=api-keys>

## 安装

从 npm 安装（预构建产物，推荐）：

```sh
dsh plugin --profile web add @jiesou/dsh-cline-free-provider
```

或从 GitHub 安装：

```sh
dsh plugin --profile web add github:jiesou/dsh-cline-free-provider
```

## 安装之后

Cline 的 API Key 通过 DSH credentials 服务保存（变量名为 `CLINE_API_KEY`，可在 Web Models 页面填写）。

模型列表**无需任何配置**，插件启动时会自动从远程同步并过滤所有免费模型。在 Web Models 页面选择 Cline provider 和模型后即可开始使用。

### 配置项

全部可选，默认即可用：

```yaml
- id: cline-free-provider
  name: '@jiesou/dsh-cline-free-provider'
  config:
    apiKeyEnv: CLINE_API_KEY
    baseURL: https://api.cline.bot/api/v1
    defaultMaxTokens: 32768
    defaultContextWindow: 262144
```

| 配置项 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `apiKeyEnv` | `string` | `"CLINE_API_KEY"` | 读取 API Key 的环境变量名（或 credential ref） |
| `baseURL` | `string` | `"https://api.cline.bot/api/v1"` | Cline 网关 base URL |
| `defaultMaxTokens` | `number` | `32768` | 模型无精确 maxTokens 时的兜底值 |
| `defaultContextWindow` | `number` | `262144` | 模型无精确 contextWindow 时的兜底值 |

## 模型目录与推理档位

插件在启动时拉一次免费模型目录，**不轮循**。上游轮换慢，一次抓取足矣。挂载时上游不可达也不挂——目录暂时为空、不会拖垮插件或模型界面。

Reasoning effort：模型只暴露上游接受的档位，不造档位。**Default** 表示"不发送 `reasoning_effort`"字段，由上游自行决定深度。**Off** 是真开关——发送上游的关闭字面值（`none`、`off` 等）。上游标记为 mandatory 的模型干脆不显示 Off 选项，插件不替它伪造一个。

错误提示：上游拒绝（已结束的免费推广、区域限制等）在终端错误事件里保留真实原因，不会被 harness 当 AUTH 吞掉。真正的鉴权失败仍按 AUTH 走，无法解析的内容原样透传。

## License

[MIT](LICENSE)
