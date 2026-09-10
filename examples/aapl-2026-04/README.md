# 案例：aapl-2026-04（AAPL · 2026-04）

一个完整的 Mira 研究包样例，演示「论点 → 证据 → 刷新 → 监控」全链路产物。
**历史案例，不构成投资建议**；`state = stale`，复用前先刷新。

## 包内文件

| 文件 | 角色 |
|---|---|
| `research-package.json` | 包清单（入口）：就绪度、阻塞缺口、产物索引、刷新边界 |
| `thesis-card.yaml` | 论点卡：core_claim / 关键变量 / 证伪条件 / 刷新条件 |
| `investment-memo.md` | 研究备忘（hero 产物，人类可读的结论面） |
| `evidence-log.csv` | 证据日志（canonical v1.2，22 列，9 条记录） |
| `refresh.yaml` | 刷新计划：4 个触发条件 + must_refresh_if |
| `monitoring.json` | 监控队列：4 个待跟踪变量 |
| `routing.json` | 路由卡：模式、深度、门禁与后续提问 |
| `refresh-report.md` / `refresh-report.json` | 刷新报告（`mira refresh --write` 生成） |
| `report.md` | 研究包读出（`mira report` 生成） |

## 复现

```bash
# 契约校验（本案例应全绿）
python -m mira validate examples/aapl-2026-04

# 刷新报告：as_of=2026-09-10 → expired（时间边界 2026-07-13 已过，且多个触发条件到期未核对）
python -m mira refresh examples/aapl-2026-04 --as-of 2026-09-10 --write

# 研究包读出
python -m mira report examples/aapl-2026-04 --as-of 2026-09-10 -o examples/aapl-2026-04/report.md
```

> 本样例由上游 `cases/aapl-2026-04` 裁剪而来：去掉了 expectation-map / decision-log / case-notes 等冗余文件，
> 其语义分别归并到 `monitoring.json`、`investment-memo.md` 的决策头与行动性桥、`thesis-card.yaml`。
