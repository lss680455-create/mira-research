# AAPL 研究备忘（2026-04 案例包）

> 历史案例，用于演示 Mira 工作流；不构成投资建议。本包 **state = stale**：复用前先跑 `mira refresh`。

## 决策头

| 项 | 值 |
|---|---|
| 标的 | AAPL（US equity） |
| 视角 / 期限 | 基本面 · 6–12 个月 |
| 调研截止 | 2026-04-14 |
| 就绪度 | `working_view`（行动性受阻：市场数据与估值语境已过期） |
| research_action | `watch_only`（研究动作，不是交易指令） |
| 行动动作 | `needs_refresh` → 刷新后再评估 |

## 核心结论

Apple 仍是高质量平台型资产：

1. **护城河来自生态与装机量** —— 软硬件 + 服务的闭环、数十亿级活跃设备，构成难复制的用户留存与定价能力（10-K）。
2. **现金流与资本回报具备长期韧性** —— 季度业绩显示利率环境下的收入/利润率韧性与强劲经营现金流，回购与分红持续（季度业绩稿）。
3. **但价格已计入『质量』** —— 2026-04 时点为溢价大市值倍数，安全边际有限；上行需要盈利上修或风险溢价压缩，仅重申质量不够。

**因此结论是「值得跟踪持有的优质平台」，不是「明显错杀的弹性机会」。**

## 多头与空头（各自最强的三个点）

| 多头 | 空头 |
|---|---|
| 生态留存 + Services 结构性增长 | 估值倍数已反映质量与资本回报韧性 |
| 现金流耐久性支撑回购与分红 | 产品周期疲劳：iPhone 增速放缓风险 |
| AI / 新品周期提供可选上行 | 监管、关税与供应链对毛利率的持续压力 |

## 估值立场

本案例**未构建估值模型**（base/bull/bear）。依据一手披露与季度数据，只给出「溢价大市值倍数、安全边际有限」的语境判断，并把它标记为 `source_gap`（见证据日志第 4 行）。构建估值模型是复用时的一号缺口。

## 证据面（9 条，v1.2 契约）

| 维度 | 分布 |
|---|---|
| evidence_category | verified_fact ×2 · reported_fact ×2 · market_pricing ×2 · inference ×2 · weak_signal ×1 |
| treatment | use_normally ×4 · source_gap ×2 · monitor ×2 · attribute ×1 |
| readiness_impact | supports_durable_conclusion ×4 · supports_working_view ×3 · monitoring_only ×1 · blocks_actionability ×1 |
| freshness_status | current ×4 · acceptable_for_period ×3 · preliminary ×1 · stale ×1 |

**被明确降级的证据**：行情类两条（`financecharts_aapl_summary`、`stockanalysis_aapl_history`）标注 `acceptable_for_period`（短周期数据，复用前必须刷新，`source_gap` / `monitor`）；合成行 `derived_aapl_apr2026_thesis` 标注 `stale`（时效跟随最短寿输入）；技术解读仅作语境（`attribute`）；折叠屏时间表传闻只进监控（`monitoring_only`，未证实）。

## 行动性桥（为什么不能直接照做）

| 缺口 | 类型 | 解除条件 |
|---|---|---|
| 当前价格 / 估值语境 | `source_gap` | 行情刷新 + 估值模型（base/bull/bear） |
| 下一份季报与指引 | `open_item` | 财报发布后核对 Services / 毛利率 / 产品排期 |
| 技术关键位（245 / 285） | `monitor` | 持续失守 → 回退研究循环 |

## 必须刷新的条件（与本包 `must_refresh_if` 一致）

- Apple 发布下一份财报或正式指引更新；
- 核心产品 / AI 节奏出现实质性变化；
- 关税、供应链或监管披露实质影响毛利率；
- 当前价格与估值语境与 2026-04 案例出现重大偏离。

## 后续提问（routing 卡 · `standard` 档）

1. 三个候选驱动（Services 韧性 / 产品周期 / 估值倍数）里，哪个作为论点轴？
2. 哪些可观测信号出现时，你认输（证伪条件）？
3. 本次优先看增长、风险还是估值？是否需要构建估值模型？
