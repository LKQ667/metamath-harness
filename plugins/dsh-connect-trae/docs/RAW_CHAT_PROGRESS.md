# Raw Chat 开发阶段交接

## 已完成

- `TraeRawChatUpstreamClient`：单v2端点、注入式fetch、超时、取消、错误分类。
- Raw Chat离线message/tool/reasoning/usage/done模型。
- 模型配置日志解析，确认预置GLM-5.2：
  - `config_name=glm-5.2`
  - `prompt_set=None`
  - `ab_versions=None`
  - `raw_chat_function=None`
- 思考强度能力模型：`minimal/low/medium/high/xhigh`，仅按模型声明开放。
- 官方machine/device ID、版本、OS、trace headers映射。
- 默认dry-run的Raw Chat和模型元数据探测器。
- CN过期access token可通过refresh token成功刷新并安全存到DSH副本。

## 受控探测结果

1. Raw Chat v2最小请求：HTTP 400，空响应体。
2. batch_get_detail_param初始请求：HTTP 400，空响应体。
3. 补齐官方headers并使用精确185字节请求体：HTTP 400，空响应体。
4. 使用刷新后的有效access token重试：仍HTTP 400，空响应体。

没有执行v1回退、Agent Task回退或批量字段枚举。

## 已排除

- CN access token过期不是唯一原因。
- mode/access枚举大小写不是原因；官方JSON长度证明数值0编码。
- `prompt_set`与`ab_version`不是预置GLM-5.2的必填非空值。
- machine/device ID形态已匹配历史官方请求。
- 通用版本、设备、OS、trace headers已补齐。

## 当前阻断条件

公开日志只显示业务headers，不显示官方HTTP层最终认证/租户字段；服务对差异统一返回400空body。继续枚举请求字段将成为无依据试错。

可能剩余项：

- `X-Trae-Authorized-Services`或租户/region信息。
- 官方transport对Authorization/CloudIDE token的特殊处理。
- 当前Trae版本的模型详情schema变更。
- boot config动态host或路由信息。

## 推荐下一步

优先从Trae新日志或可控调试环境获得官方HTTP客户端的最终request header names/body shape；或者在用户明确授权后，仅对一个高证据差异做一次探测。取得模型详情后，先解析reasoning effort矩阵，再启用Raw Chat client。
