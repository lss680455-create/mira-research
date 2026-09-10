# 研究包读出 · aapl-2026-04

- 目录: `examples\aapl-2026-04`
- as_of: 2026-09-10

## 包概览

| 字段 | 值 |
| --- | --- |
| 研究对象 | AAPL |
| 市场范围 | US equity |
| 调研截止日 | 2026-04-14 |
| 包类型 | research_package |
| 就绪度 | working_view |
| 主工作流 | workflows/research-loop.md |
| 证据表状态 | canonical_v1_2 |
| 时间边界 | 2026-07-13 |

## 产物清单

- [✓] `investment-memo.md`（hero）
- [✓] `refresh-report.md`（hero）
- [✓] `evidence-log.csv`（support）
- [✓] `thesis-card.yaml`（support）
- [✓] `routing.json`（support）
- [✓] `refresh.yaml`（support）
- [✓] `monitoring.json`（support）
- [✓] `report.md`（support）

## 论点状态

- 状态: stale（置信度 medium）
- 核心主张: Apple 仍是高质量平台型资产：品牌、软硬件生态与 20 亿级活跃设备构成难复制的护城河， 现金流与资本回报具备长期韧性；但 2026-04 时点的价格已基本反映其质量， 属于「值得跟踪持有的优质平台」，而非「明显错杀的弹性机会」。

| 变量 | 共识锚点 | Mira 视角 | 定价程度 |
| --- | --- | --- | --- |
| Services 增长与利润率韧性 | 市场共识预期 Services 继续支撑增长与利润率 | Services 是耐久性支柱，需持续监控监管与结构压力 | partly_price_in |
| iPhone 产品周期延续性 | 市场围绕 iPhone 周期、AI 路线图与新品节奏反复定价 | 周期风险真实存在，但本论点不依赖单一产品催化 | partly_price_in |
| 估值倍数与风险溢价 | 大市值公司估值已计入质量与资本回报韧性 | 上行需要盈利上修或风险溢价压缩，仅重申质量不够 | mostly_price_in |

## 证据面

- 行数: 9（表头版本 v1.2）
- 证据类别: inference×2，market_pricing×2，reported_fact×2，verified_fact×2，weak_signal×1
- 处理方式: attribute×1，monitor×2，source_gap×2，use_normally×4
- 过期行: 1 条
- 阻塞行: 1 条

## 刷新状态

- 计算状态: 已过期（来源：时间边界+到期未核对）
- 距时间边界: 已超出 59 天（stale_after=2026-07-13）

- [ ] 时间边界已过（stale_after=2026-07-13）：先用最新数据复核再引用本结论
- [ ] 补做到期核对 T1-time（next_check=2026-07-13）
- [ ] 补做到期核对 T3-price（next_check=2026-07-31）
- [ ] 补做到期核对 T4-policy（next_check=2026-07-31）
- [ ] 更新已过期证据行：derived_aapl_apr2026_thesis（Integrated thesis as of 2026-04-14: qual…）
- [ ] 按计划核对 T2-earnings（next_check=2026-10-30）

## 监控队列

| 变量 | 来源 | 频率 | 状态 | 升级条件 |
| --- | --- | --- | --- | --- |
| Services 收入与毛利率 | 季度财报 / 10-Q 分部披露 | quarterly | open | Services 增速或毛利率连续两个季度弱于指引区间 |
| iPhone 需求与产品排期 | 财报电话会、供应链报道与产品发布 | quarterly | open | 出现可信的周期走弱证据，或多季度需求下滑 |
| 关税 / 监管对毛利率的影响 | 公司披露、监管公告与政策新闻 | event_driven | open | 披露显示毛利率耐久性受到实质影响 |
| 股价关键位与估值语境 | 行情数据（245 支撑 / 285 压力） | weekly | open | 有效跌破 245 并持续失守，或估值语境出现重大偏离 |

## 路由卡片

- 交互模式: routed_research
- 任务类型: first_pass_research
- 深度: standard
- 决策压力: none
- 计算依赖: high
- 主工作流: workflows/research-loop.md

追问清单:
- Q2 主线变量（rung: 核心）——三个候选驱动（Services 韧性 / 产品周期 / 估值倍数）里，哪一个作为本论点的轴？
- Q5 证伪条件（rung: 核心）——哪些可观测信号（Services 增速、毛利率、产品排期、监管披露）出现时你认输？
- Q6 产出取向（rung: 常规）——本次优先看增长、风险还是估值？是否需要构建 base/bull/bear 估值模型？
