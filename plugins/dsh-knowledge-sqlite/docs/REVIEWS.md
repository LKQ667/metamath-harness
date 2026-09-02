# 评审链摘要：Memory Knowledge Seam（11 轮，0C / 0M / 0m 收敛）

> dsh-knowledge-sqlite 的设计文档（`docs/DESIGN.md`）经过 **11 轮评审-裁决循环**收敛，
> 最终状态 **0 Critical / 0 Major / 0 Minor**。本文为逐轮摘要；
> 完整裁决文档存于 `research/memory-knowledge-seam/review/adjudications/`（每版本一份）与
> `research/memory-knowledge-seam/review/{redteam,blueteam,final-adjudication}-v4pro.md`。

## 评审链结构

```
V1.0 初始提案 → V1.1 完整规格（契约/数据流/备选/AC/测试矩阵）
 → V1.2 架构评审 + 红队（指标修正、配置重排、对照臂、授权、update/dedupeKey、TTL、级联）
 → V1.3 裁决澄清（所有权打标、模型回退、tokenMeter 命名、PRF 资格、工具路径截断）
 → V1.4 红蓝轮（信任模型 + authorTier、三层授权、tombstone、分页、幂等、规模预算）
 → V1.5 v4-pro 终审（富化幂等恢复、AC 均值±范围语义、p95/timeoutMs 头部、契约打标字段、检索 schema 预算）
 → V1.6 裁决（人类集 L1 修正 82%、打标字段工具层所有 + 伪造拒绝、update 授权 + scope/dedupeKey 不可变、
        人类集 precision@1 ≥80% 门禁、PRF 回退 + rank-3 翻转、oversized 丢弃、MRR 对账）
 → V1.7 裁决（受信内部写者、precision@5 绑定条件、测试矩阵补行、人类集 C/D 臂方差条款）
 → V1.8 裁决（写者注册语义、人类集方差下限均值化 + 临时单次下限）
 → V1.9 裁决（修订日志补录、zh References 协议链镜像）
 → V1.10 裁决（References 目录引用去版本枚举、zh 双句号）
 → V1.11 终审（两项 minor 关闭确认；红队残留扫描零发现；279/279 行双语一致（2026-08-14 时点；现行 DESIGN.md 285 行））
```

## 逐轮裁决表

| 版本 | 裁决 | 关键处理 |
|---|---|---|
| V1.1 | 规格建立 | 完整契约：write/update/search/list/delete + budget + 事件 + 错误码；测试矩阵 |
| V1.2 | 架构+红队 | 修正 7/29/36/64 指标；配置重排；加对照臂；授权/update/dedupeKey/TTL/级联明确 |
| V1.3 | 澄清 | 所有权打标（工具层）；模型回退（不静默降级 L0）；PRF 仅 rank-3 候选；路径截断归工具层 |
| V1.4 | 红蓝 | 信任模型 authorTier 四档；三层授权（workspace/preset/approval）；tombstone；分页；幂等声明收敛；规模预算 |
| V1.5 | v4-pro 终审 | FAIL（4 major + 7 minor）→ 富化幂等恢复；AC 改均值±范围；p95 2.0s < timeoutMs 2.5s；打标字段工具层所有；检索预算封顶 |
| V1.6 | 裁决 | 人类集 L1 修正 82%；打标伪造拒绝；update 授权 + scope/dedupeKey 不可变；人类集 precision@1 ≥80%；PRF 回退 + rank-3 翻转；MRR 对账 |
| V1.7 | 裁决（PASS, 5 minors） | 受信内部写者档位；precision@5 ≥0.3 绑定（先测后绑）；矩阵补 stamp 拒绝/scope 不可变/update→global 复检；人类集 C/D 臂方差条款 |
| V1.8 | 裁决（PASS, 3 minors） | 写者注册语义（phase-2 前置）；人类集方差下限均值化 + 临时单次下限；协议裁决链入 References |
| V1.9 | 裁决（PASS, 2 minors） | V1.8 日志补录；zh References 协议链镜像 |
| V1.10 | 裁决（PASS, 2 minors） | References 去版本枚举（纯目录引用）；zh 双句号 |
| **V1.11** | **终审（PASS, 0 remaining）** | 两项 minor 关闭确认；红队残留扫描零发现；双语 279/279 行一致（2026-08-14 时点；现行 DESIGN.md 285 行） |

**最终状态：0 Critical / 0 Major / 0 Minor**（截至 V1.11，2026-08-14）。

## 附加评审（V1.4 前后）

- 独立架构评审（deepseek-v4-flash）：`research/memory-knowledge-seam/review/adjudication-v4pro.md` 前身阶段
- 红队 / 蓝队（v4-flash 子代理 + deepseek-v4-pro 直连）：`research/memory-knowledge-seam/review/redteam-v4pro.md` / `research/memory-knowledge-seam/review/blueteam-v4pro.md`
- v4-pro 终审：`research/memory-knowledge-seam/review/final-adjudication-v4pro.md`
- 红蓝对抗总结：`research/memory-knowledge-seam/review/red-blue-summary.md`

## 验收门禁（V1.11 AC，实现侧状态）

| 门禁 | 目标 | 实现侧状态（2026-08-14） |
|---|---|---|
| L1 recall@1（hard 难查询） | ≥30% 均值（无单次 <20%） | 动态原型 43%/64%；宿主 bundle L1-live 64%（方差 10 轮均值 49% 范围 36-71%，见 EXPERIMENTS §7.2） |
| human 集 L1 | ≥50%（均值） | 宿主 65% ✓ |
| 人类集 precision@1 | ≥80%（信息性） | A 65% / L1-live 59%（单目标套件口径 ≡ recall@1，信息性，见 EXPERIMENTS §6） |
| p95 L1 延迟 | ≤2.0s（4 路并发，人类查询集） | 已测且 FAIL：fresh p95 2171-2380ms > 2000ms，缓存口径 ≈0（见 EXPERIMENTS §5/§6/§8） |
| 写入即检索（零 LLM） | AC | 宿主验证 ✓ |
| 授权/打标/错误码/事件 | AC | contract 12/12 ✓ |
| 实验套件入库可复现 | AC | research/memory-knowledge-seam/experiments/memory-experiment/ + knowledge_probe ✓ |
