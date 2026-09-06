# Trae 用量管理 API 调查

> 只记录脱敏结构、字段名、数值与行为。不得复制 token、用户消息正文、账号信息或完整请求 body。

## 目标

确认能否用插件现有的 `Cloud-IDE-JWT` 凭据读取 Trae 「用量管理」数据（总可用额度、积分来源、签到、消费明细），以及每一步的证据与结论。

## 结论速览

| 数据 | 接口 | 结果 |
|---|---|---|
| 总可用额度 / 已消耗 / 比例 | `POST /trae/api/v2/pay/web_user_ent_usage`（别名 `user_current_entitlement_list`） | ✅ 可调，与截图精确一致 |
| 各项积分来源（老用户/签到/登录赠送/免费） | 同上 pack 列表 | ✅ |
| 计费状态（积分计费） | `POST /trae/api/v2/pay/cn_credits_billing_status` | ✅ `is_credits_billing: true` |
| 权益/活动规则 | `POST /trae/api/v2/pay/web_user_pay_status` | ✅ |
| 过期权益 | `POST /trae/api/v2/pay/expired_ents` | ✅ `{expired_ent_list: []}` |
| 每日签到状态 | `POST /trae/api/v2/ug/checkin_credits/status` | ✅ |
| 奖励活动规则 | `POST /trae/api/v2/ug/activity/info` | ✅ |
| **每笔消费明细表** | `POST /trae/api/v1/pay/query_user_usage_group_by_session` | ⚠️ HTTP 200 但 `total: 0`，拿不到 |

所有成功接口均为**只读查询，不消耗 Trae 积分**。

## 认证与 Host

- 凭据：桌面 `solo` edition 的 `Cloud-IDE-JWT` access token（插件 `auth.ts` 解析），host 为 `https://api.trae.cn`。
- 认证方式：`Authorization: Cloud-IDE-JWT <token>`，与聊天通道一致；与网页登录态（Cookie）是两套体系。
- 页面来源用 `Origin/Referer: https://www.trae.cn/` 与桌面 User-Agent 均可。

## 额度接口（核心，已验证）

`POST https://api.trae.cn/trae/api/v2/pay/web_user_ent_usage`
Body: `{"require_usage": true}`

返回顶层结构：

```text
is_credits_billing      true
is_dollar_usage_billing false
is_pay_freshman         true
trial_status            {is_eligible_for_trial:false, is_in_trial:false}
usage_summary           {consumed_amount, consumption_ratio, total_amount}
user_entitlement_pack_list[]
```

关键数值（本机实测）：

```text
total_amount    = 7500
consumed_amount = 5879.63
consumption_ratio = 0.78395...
可用            = total - consumed = 1620.37   ← 与截图"总可用额度 1,620.37"精确一致
```

### pack 列表（对应截图的积分来源）

| display_desc | currency | credits_limit | 说明 |
|---|---|---|---|
| 老用户福利 | 1 | 2000 | entitlement 326737122050 |
| 老用户福利 | 1 | 2000 | entitlement 326737122306 |
| 免费 | 0 | — | `free_utc20268_...` |
| 每月登录赠送 | 1 | 500 | `monthly_bonus_...` |
| 签到奖励 | 1 | 200 | `checkin_YYYYMMDD_...` 多笔（08-20 一笔已用剩 179.63） |

pack 内 `usage.credits_amount` 表示该套餐当前剩余积分。

## 其它已验证接口

- `POST /trae/api/v2/pay/cn_credits_billing_status` → `{is_credits_billing: true, should_force_switch: true}`
- `POST /trae/api/v2/pay/user_current_entitlement_list` → 与 web_user_ent_usage 相同结构（别名）
- `POST /trae/api/v2/pay/web_user_pay_status` → `client_reminder` + `commercial_activities`（express_lottery、work_fission、new_user_credits 等）
- `POST /trae/api/v2/pay/expired_ents` → `{expired_ent_list: []}`
- `POST /trae/api/v2/ug/checkin_credits/status` → `{checked_in: true, credits: 200, code: 0}`
- `POST /trae/api/v2/ug/activity/info` → `commercial_activities`（checkin_credits 200、new_user_credits 2000+2000、send_message_reward 500 等）

## 消费明细表（未拿到）

`POST https://api.trae.cn/trae/api/v1/pay/query_user_usage_group_by_session`

参数（来自 `www.trae.cn` 前端 bundle）：

```text
start_time, end_time, page_size, page_num, usage_type, Request
```

实测：
- 不传 `usage_type` → HTTP 200，`{"total":0, "user_usage_group_by_sessions":[]}`（多种时间窗、秒/毫秒、page_size、带不带 Request 均如此）。
- 传 `usage_type`（0/1/2/3 或字符串）→ HTTP 400（参数不合法）。

结论：认证通、接口存在，但当前账号/时间窗下不返回明细。截图里那些「DeepSeek-V4-Flash 0.09 / GLM-5.3 669.58」的记录无法从该接口复现。判断该明细可能属于另一产品端（Solo/TraeWork）或需要网页登录态下的其它接口；不继续无依据试错。

## 网页浏览调查

- `www.trae.cn/dashboard` 在无登录态下重定向到登录页（手机验证码/抖音/苹果/企业账号），走 Cookie 会话认证，与插件的 `Cloud-IDE-JWT` 是两套体系；无法代用户登录。
- `www.trae.cn` 前端 bundle 的 API client 统一注入 `Authorization: Cloud-IDE-JWT`，baseURL 为 `api.trae.cn`（`c.QU`）。
- 埋点/统计请求（`mcs.zijieapi.com`、`clarity.ms`、`bing`、`monitor_browser`）不含用量数据，可忽略。
- 从 Network 实测确认：用量页真正的数据请求就是 `api.trae.cn/trae/api/v2/pay/*`（已全部复现）和 `query_user_usage_group_by_session`（明细，空）。

## 建议下一步

1. ~~将已验证的额度/积分/签到/活动接口封装为插件只读命令（如 `trae.usage`）~~ **已完成（2026-08-28）**：
   - 新增 `src/usage.ts` 的 `TraeUsageClient`（只读，注入式 fetch），提供：
     - `snapshot()` —— 总可用额度、已消耗、各项积分来源与剩余
     - `checkinStatus()` —— 每日签到状态
     - `activities()` —— 奖励活动规则
     - `view()` —— 三者聚合
   - 已在 `tests/usage.spec.ts` 覆盖解析逻辑；`pnpm run check` 通过（19 测试文件、60 测试、typecheck 与 build 成功）。
   - 真实验证（本机 solo 凭据）：总可用 1620.37、签到 `checked_in:true`、packs 与活动规则均正常返回；只读、未消耗积分。
2. 消费明细表待拿到 Solo/TraeWork 网页版真实明细接口（需登录态）后再接入；不阻塞额度能力。
3. 所有新增接口遵循既有安全原则：只读、不写日志、不缓存 secret、脱敏输出。
