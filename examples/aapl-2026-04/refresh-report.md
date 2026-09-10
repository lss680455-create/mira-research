# 刷新报告 · AAPL：高质量平台资产的中长线持有逻辑（2026-04 案例）

- thesis_id: `aapl-2026-04`
- as_of: 2026-09-10
- stale_after: 2026-07-13
- 计算状态: 已过期（expired）（来源：时间边界+到期未核对）
- 计划声明状态: fresh（以计算状态为准）
- 距时间边界: 已超出 59 天
- due_soon 判定窗口: 到期前 30 天

## 触发条件核对

| 条件 | 类型 | 状态 | 下次核对 | 触发条件 |
| --- | --- | --- | --- | --- |
| T1-time | time | pending（已到期待核对） | 2026-07-13 | 到达时间边界 2026-07-13（与下一份财报先到者为准） |
| T2-earnings | filing | pending | 2026-10-30 | Apple 发布下一份季度财报或正式指引更新 |
| T3-price | price | pending（已到期待核对） | 2026-07-31 | AAPL 有效跌破 245 美元附近关键支撑并持续失守 |
| T4-policy | event | pending（已到期待核对） | 2026-07-31 | 关税、监管或供应链披露实质影响毛利率 |

## 必须刷新的条件

- Apple 发布下一份财报或正式指引更新
- 核心产品 / AI 节奏出现实质性变化
- 关税、供应链或监管披露实质影响毛利率
- 当前价格与估值语境与 2026-04 案例出现重大偏离

## 证据面速览

- 行数: 9（表头版本 v1.2）
- 新鲜度分布: acceptable_for_period×3，current×4，preliminary×1，stale×1
- 过期行: derived_aapl_apr2026_thesis（Integrated thesis as of 2026-04-14: qual…）

## 下一步动作

- [ ] 时间边界已过（stale_after=2026-07-13）：先用最新数据复核再引用本结论
- [ ] 补做到期核对 T1-time（next_check=2026-07-13）
- [ ] 补做到期核对 T3-price（next_check=2026-07-31）
- [ ] 补做到期核对 T4-policy（next_check=2026-07-31）
- [ ] 更新已过期证据行：derived_aapl_apr2026_thesis（Integrated thesis as of 2026-04-14: qual…）
- [ ] 按计划核对 T2-earnings（next_check=2026-10-30）

## 说明

refresh.yaml 是计划快照：refresh_status 为计划时点（2026-04-14）的状态；实际状态一律以 `mira refresh` 计算为准。
